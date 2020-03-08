import argparse
import logging
import sys
import traceback
import warnings
from collections import namedtuple
from typing import Iterable, Optional, Union, List, Dict, Any, Iterator
import os
import threading
import time

import pymysql
import progressbar
from abc import ABC
from enum import IntEnum

from helpers import mapsHelper
from helpers.config import Config
from objects import beatmap
from objects import score
from common.db import dbConnector
from objects import glob


MAX_WORKERS = 32
UNIX = os.name == "posix"
FAILED_SCORES_LOGGER = None


RecalculatorQuery = namedtuple("RecalculatorQuery", "query parameters")


class WorkerStatus(IntEnum):
    NOT_STARTED = 0
    WORKING = 1
    DONE = 2


class Recalculator(ABC):
    """
    Base PP Recalculator
    """
    def __init__(self, ids_query: RecalculatorQuery, count_query: RecalculatorQuery):
        """
        Instantiates a new recalculator

        :param ids_query: `RecalculatorQuery` that fetches the `id`s of the scores of which pp will be recalculated
        :param count_query: `RecalculatorQuery` that counts the _total_ number of the scoresof which pp will be
        recalculated
        """
        self.ids_query: RecalculatorQuery = ids_query
        self.count_query: RecalculatorQuery = count_query


class SimpleRecalculator(Recalculator):
    """
    A simple recalculator that can use a set of simple conditions, joined with logic ANDs
    """
    def __init__(
        self,
        conditions: Union[Iterable[str], str],
        parameters: Optional[Union[Iterable[str], Dict[str, Any]]] = None
    ):
        """
        Initializes a new SimpleRecalculator

        :param conditions: The conditions that will be joined with login ANDs.
        They can be:
        * an iterable (list, tuple, ...) of str (multiple conditions)
        * str (one condition)
        :param parameters: Iterable (list, tuple, ...) or dict that contains the query's parameters.
        These will be passed to MySQLdb to bind the query's parameters (%s and %(name)s)
        """
        if type(conditions) in (list, tuple):
            conditions_str = " AND ".join(conditions)
        elif type(conditions) is str:
            conditions_str = conditions
        else:
            raise TypeError("`conditions` must be either a `str`, `tuple` or `list`")
        q = "SELECT {} FROM scores JOIN beatmaps USING(beatmap_md5) WHERE {} ORDER BY scores.id DESC"
        super(SimpleRecalculator, self).__init__(
            ids_query=RecalculatorQuery(q.format("scores.id AS id", conditions_str), parameters),
            count_query=RecalculatorQuery(q.format("COUNT(*) AS c", conditions_str), parameters)
        )


class ScoreIdsPool:
    """
    Pool of score ids that needs to be recalculated.
    """
    logger = logging.getLogger("score_ids_pool")

    def __init__(self):
        """
        Initializes a new pool
        """
        self._lock = threading.Lock()
        self.scores: List[int] = []

    def load(self, recalculator: Recalculator):
        """
        Loads score ids in the pool from a Recalculator instance

        :param recalculator: The recalculator instance that will be used to fetch the score ids
        :return:
        """
        with self._lock:
            query_result = glob.db.fetchAll(recalculator.ids_query.query, recalculator.ids_query.parameters)
            self.scores += [x["id"] for x in query_result]
        self.logger.debug("Loaded {} scores".format(len(self.scores)))

    def __iter__(self) -> Iterator[int]:
        for x in self.scores:
            with self._lock:
                yield x


class Worker:
    """
    A tomejerry worker. Recalculates pp for a set of scores.
    """
    processed_scores_count = 0
    recalculated_scores_count = 0
    failed_scores_count = 0

    processed_scores_count_lock = threading.Lock()
    recalculated_scores_count_lock = threading.Lock()
    failed_scores_count_lock = threading.Lock()

    def __init__(self, pool_iter, *, worker_id: int = -1, start: bool = True, no_download: bool = False):
        """
        Initializes a new worker.

        :param worker_id: This worker's id. Optional. Default: -1.
        :param start: Whether to start the worker immediately or not
        :param no_download: If True, do not attempt to download non-existing maps.
        :param
        """
        self.pool_iter = pool_iter
        self.worker_id: int = worker_id
        self.thread: Optional[threading.Thread] = None
        self.logger: logging.Logger = logging.getLogger("w{}".format(worker_id))
        self.status: WorkerStatus = WorkerStatus.NOT_STARTED
        self.no_download: bool = no_download
        if start:
            self.threaded_work()

    @staticmethod
    def recalc_score(score_data: Dict, no_download=False) -> Optional[score.score]:
        """
        Recalculates pp for a score

        :param score_data: dict containing score and beatmap information about a score.
        :param no_download: if True, raise FileNotFoundError() if the map should be re-downloaded.
                            this ensures no requests are made to osu!
        :return: new `score` object, with `pp` attribute set to the new value
        """
        # Create score object and set its data
        s: score.score = score.score()
        s.setDataFromDict(score_data)
        s.passed = True

        # Create beatmap object and set its data
        b: beatmap.beatmap = beatmap.beatmap()
        b.setDataFromDict(score_data)

        # Abort if we are running in no_download mode and the map should be re-downloaded
        if no_download and mapsHelper.shouldDownloadMap(mapsHelper.cachedMapPath(b.beatmapID), b):
            raise FileNotFoundError("no_download mode and local map not found")

        # Calculate score pp
        s.calculatePP(b)
        del b
        return s

    def _work(self, close_connection: bool = True):
        """
        Run worker's work. Fetches scores, recalculates pp and saves the results in the database.

        :return:
        """
        # Make sure the worker hasn't been disposed
        if self.status == WorkerStatus.DONE:
            raise RuntimeError("This worker has been disposed")

        self.logger.info("Started worker.")
        try:
            # Recalculate all pp and store results in db
            self.recalculate_pp()
        finally:
            # Mark the worker as disposed at the end
            self.logger.debug("Disposing worker")
            # Close the thread-local connection at the of the thread
            if close_connection:
                glob.threadScope.dbClose()
            self.status = WorkerStatus.DONE

    def recalculate_pp(self):
        """
        Recalculates the pp and saves results in memory

        :return:
        """
        # We cannot use a SSDictCursor directly, because the connection will time out
        # if the cursor doesn't consume every result before the `wait_timeout`, which is
        # 600 seconds in MariaDB's default configuration. This means that we have to recalculate
        # PPs for all scores in no more than 600 seconds, or we'll get a 'MySQL server has
        # gone away error'. Fetching every score (joined with the respective beatmap)
        # directly would take up too much RAM, so we fetch all the score_ids at the
        # beginning with one query, store them in memory and fetch the data for
        # each score, one by one, using the same connection (to avoid pool overhead)
        self.status = WorkerStatus.WORKING
        # self.recalculated_scores_count = 0

        # Fetch all score_ids
        # self.scores = [LwScore(x["id"], 0) for x in glob.db.fetchAll(self.ids_query.query, self.ids_query.parameters)]

        # Get a db worker
        db_connection = glob.threadScope.db
        cursor = None

        try:
            # Get a cursor (normal DictCursor)
            cursor = db_connection.cursor(pymysql.cursors.DictCursor)
            for score_id in self.pool_iter:
                # Fetch score and beatmap data for this id
                cursor.execute(
                    "SELECT * FROM scores JOIN beatmaps USING(beatmap_md5) WHERE scores.id = %s LIMIT 1",
                    (score_id,)
                )
                score_ = cursor.fetchone()
                try:
                    # Recalculate pp
                    try:
                        s = Worker.recalc_score(score_, no_download=self.no_download)
                    except FileNotFoundError as e:
                        if self.no_download:
                            # No map found locally
                            self.log_failed_score(score_, str(e))
                            continue

                        # Not running in no_download mode, something else happened. Re-raise.
                        raise e

                    if s.pp == 0:
                        # PP calculator error
                        self.log_failed_score(score_, "0 pp")

                    # Update in db
                    self.logger.debug(f"Updating {score_id} = {s.pp}")
                    cursor.execute("UPDATE scores SET pp = %s WHERE id = %s LIMIT 1", (s.pp, score_id))
                    with Worker.recalculated_scores_count_lock:
                        Worker.recalculated_scores_count += 1

                    # Mark for garbage collection
                    del s
                except Exception as e:
                    self.log_failed_score(score_, str(e), traceback_=True)
                finally:
                    del score_
                    with Worker.processed_scores_count_lock:
                        Worker.processed_scores_count += 1
                    if Worker.processed_scores_count % 1000 == 0:
                        self.logger.info(f"Processed {Worker.processed_scores_count} scores")
        finally:
            # Close cursor and connection
            if cursor is not None:
                cursor.close()
            self.logger.debug("PP Recalculated")

    def threaded_work(self):
        """
        Starts this worker's work in a new thread

        :return:
        """
        self.thread = threading.Thread(target=self._work)
        self.thread.start()

    def log_failed_score(self, score_: Dict[str, Any], additional_information: str = "", traceback_: bool = False):
        """
        Logs a failed score.

        :param score_: score dict (from db) that triggered the error
        :param additional_information: additional information (type of error)
        :param traceback_: Whether the traceback should be logged or not.
        It should be `True` if the logging was triggered by an unhandled exception
        :return:
        """
        msg = ""
        if traceback_:
            msg = "\n\n\nUnhandled exception: {}\n{}".format(sys.exc_info(), traceback.format_exc())
        msg += "score_id:{} ({})".format(score_["id"], additional_information).strip()
        FAILED_SCORES_LOGGER.error(msg)
        with self.failed_scores_count_lock:
            self.failed_scores_count += 1


def mass_recalc(
    recalculator: Recalculator, workers_number: int = MAX_WORKERS,
    no_download: bool = False,
) -> None:
    """
    Recalculate performance points for a set of scores, using multiple workers

    :param recalculator: the recalculator that will be used
    :param workers_number: the number of workers to spawn
    :param no_download: If True, do not attempt to download non-existing maps.
    :return:
    """
    start_time = time.time()
    global FAILED_SCORES_LOGGER
    workers = []

    if no_download:
        logging.warning("Running in no download mode.")

    logging.info("Query: {} ({})".format(recalculator.ids_query.query, recalculator.ids_query.parameters))

    # Fetch the total number of scores
    total_scores = glob.db.fetch(recalculator.count_query.query, recalculator.count_query.parameters)
    if total_scores is None:
        logging.warning("No scores to recalc.")
        return

    # Set up failed scores logger (creates file too)
    FAILED_SCORES_LOGGER = logging.getLogger("failed_scores")
    FAILED_SCORES_LOGGER.addHandler(
        logging.FileHandler("tomejerry_failed_scores_{}.log".format(time.strftime("%d-%m-%Y--%H-%M-%S")))
    )

    # Get the number of total scores from the result dict
    total_scores = total_scores[next(iter(total_scores))]
    logging.info("Total scores: {}".format(total_scores))
    if total_scores == 0:
        return

    # scores_per_worker = math.ceil(total_scores / workers_number)
    logging.info("Using {} workers".format(workers_number))

    # Load score ids in the pool
    logging.info("Filling score ids pool")
    score_ids_pool = ScoreIdsPool()
    score_ids_pool.load(recalculator)
    it = iter(score_ids_pool)

    # Spawn the workers and start them
    for i in range(workers_number):
        workers.append(
            Worker(
                it,
                worker_id=i,
                no_download=no_download,
                start=True
            )
        )

    # Progress bar loop
    recycles = 0
    widgets = [
        "[ ", "Starting", " ]",
        progressbar.FormatLabel(" %(value)s/%(max)s "),
        progressbar.Bar(marker="#", left="[", right="]", fill="."),
        progressbar.Percentage(),
        " (", progressbar.ETA(), ") "
    ]
    with progressbar.ProgressBar(
        widgets=widgets,
        max_value=total_scores,
        redirect_stdout=True,
        redirect_stderr=True
    ) as bar:
        while True:
            # Output total status information
            widgets[1] = "Recalculating pp"
            bar.update(Worker.processed_scores_count)

            # Exit from the loop if every worker has finished its work
            workers_done = [x for x in workers if x.status == WorkerStatus.DONE]
            if len(workers_done) == len(workers):
                break

            # Wait and update the progress bar again
            time.sleep(1)

    # Recalc done. Print some stats
    end_time = time.time()
    logging.info(
        "\n\nDone!\n"
        ":: Recalculated\t{} scores\n"
        ":: Failed\t{} scores\n"
        ":: Total\t{} scores\n\n"
        ":: Took\t{:.2f} seconds".format(
            total_scores - Worker.failed_scores_count,
            Worker.failed_scores_count,
            total_scores,
            end_time - start_time
        )
    )


def main():
    # CLI stuff
    parser = argparse.ArgumentParser(description="pp recalc tool for ripple, new version.")
    recalc_group = parser.add_mutually_exclusive_group(required=False)
    recalc_group.add_argument(
        "-r", "--recalc", help="calculates pp for all high scores", required=False, action="store_true"
    )
    recalc_group.add_argument(
        "-z", "--zero", help="calculates pp for 0 pp high scores", required=False, action="store_true"
    )
    recalc_group.add_argument("-i", "--id", help="calculates pp for the score with this score_id", required=False)
    recalc_group.add_argument(
        "-m", "--mods", help="calculates pp for high scores with these mods (flags)", required=False
    )
    recalc_group.add_argument(
        "-x", "--relax", help="calculates pp for relax/autopilot scores (is_relax = 1)", required=False,
        action="store_true"
    )
    recalc_group.add_argument(
        "-g", "--gamemode", help="calculates pp for scores played on this game mode (std:0, taiko:1, ctb:2, mania:3)",
        required=False
    )
    recalc_group.add_argument(
        "-u", "--userid", help="calculates pp for high scores set by a specific user (user_id)", required=False
    )
    recalc_group.add_argument(
        "-b",
        "--beatmapid",
        help="calculates pp for high scores played on a specific beatmap (beatmap_id)",
        required=False
    )
    recalc_group.add_argument(
        "-fhd", "--fixstdhd", help="calculates pp for std hd high scores (14/05/2018 pp algorithm changes)",
        required=False, action="store_true"
    )
    parser.add_argument("-w", "--workers", help="number of workers. {} by default. Max {}".format(
        MAX_WORKERS // 2, MAX_WORKERS
    ), required=False)
    parser.add_argument("-v", "--verbose", help="verbose/debug mode", required=False, action="store_true")
    parser.add_argument(
        "-nodl",
        "--no-download",
        help="do not download non-existing maps. This will cause all scores on non-cached "
             "map to fail, but will speed everything up if all maps are present.",
        required=False,
        action="store_true"
    )
    args = parser.parse_args()

    # Logging
    progressbar.streams.wrap_stderr()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    logging.root.setLevel(level=logging.DEBUG if args.verbose else logging.INFO)
    logging.info("Running under {}".format("UNIX" if UNIX else "WIN32"))

    # Load config
    logging.info("Reading config file")
    glob.conf = Config()

    # Get workers from arguments if set
    workers_number = MAX_WORKERS // 2
    if args.workers is not None:
        workers_number = int(args.workers)

    # Disable MySQL db warnings (it spams 'Unsafe statement written to the binary log using statement...'
    # because we use UPDATE with LIMIT 1 when updating performance points after recalculation
    warnings.filterwarnings("ignore", category=pymysql.Warning)

    # Connect to MySQL
    logging.info("Connecting to MySQL db")
    glob.db = dbConnector.db(
        host=glob.conf["DB_HOST"],
        port=glob.conf["DB_PORT"],
        user=glob.conf["DB_USERNAME"],
        password=glob.conf["DB_PASSWORD"],
        database=glob.conf["DB_NAME"],
        autocommit=True,
        charset="utf8",
    )

    # Set verbose
    glob.conf["DEBUG"] = args.verbose

    # Get recalculator
    recalculators_gen = {
        "zero": lambda: SimpleRecalculator(("scores.completed = 3", "pp = 0")),
        "recalc": lambda: SimpleRecalculator(("scores.completed = 3",)),
        "mods": lambda: SimpleRecalculator(("scores.completed = 3", "mods & %s > 0"), (args.mods,)),
        "id": lambda: SimpleRecalculator(("scores.id = %s",), (args.id,)),
        "gamemode": lambda: SimpleRecalculator(("scores.completed = 3", "scores.play_mode = %s",), (args.gamemode,)),
        "userid": lambda: SimpleRecalculator(("scores.completed = 3", "scores.userid = %s",), (args.userid,)),
        "beatmapid":
            lambda: SimpleRecalculator(("scores.completed = 3", "beatmaps.beatmap_id = %s",), (args.beatmapid,)),
        "fixstdhd": lambda: SimpleRecalculator(("scores.completed = 3", "scores.play_mode = 0", "scores.mods & 8 > 0")),
        "relax": lambda: SimpleRecalculator(("scores.is_relax = 1", "scores.completed = 3"))
    }
    recalculator = None
    for k, v in vars(args).items():
        if v is not None and ((type(v) is bool and v) or type(v) is not bool):
            if k in recalculators_gen:
                recalculator = recalculators_gen[k]()
                break

    # Execute mass recalc
    if recalculator is not None:
        mass_recalc(recalculator, workers_number, no_download=args.no_download)
    else:
        logging.warning("No recalc option specified")
        parser.print_help()


if __name__ == "__main__":
    main()
