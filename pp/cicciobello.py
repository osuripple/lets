import contextlib

from common.log import logUtils as log
from common.constants import gameModes, mods
from constants import exceptions
from helpers import mapsHelper
from objects import glob

from pp.catch_the_pp.osu_parser.beatmap import Beatmap as CalcBeatmap
from pp.catch_the_pp.osu.ctb.difficulty import Difficulty
from pp.catch_the_pp import ppCalc

stats = {
    "latency": {
        "classic":glob.stats["pp_calc_latency_seconds"].labels(game_mode="ctb", relax="0"),
        "relax": glob.stats["pp_calc_latency_seconds"].labels(game_mode="ctb", relax="1")
    },
    "failures": {
        "classic": glob.stats["pp_calc_failures"].labels(game_mode="ctb", relax="0"),
        "relax": glob.stats["pp_calc_failures"].labels(game_mode="ctb", relax="1"),
    }
}


class Cicciobello:
    def __init__(self, beatmap_, score_=None, accuracy=1, mods_=mods.NOMOD, combo=None, misses=0, tillerino=False):
        # Beatmap is always present
        self.beatmap = beatmap_

        # If passed, set everything from score object
        self.score = None
        if score_ is not None:
            self.score = score_
            self.accuracy = self.score.accuracy
            self.mods = self.score.mods
            self.combo = self.score.maxCombo
            self.misses = self.score.cMiss
        else:
            # Otherwise, set acc and mods from params (tillerino)
            self.accuracy = accuracy
            self.mods = mods_
            self.combo = combo
            if self.combo is None or self.combo < 0:
                self.combo = self.beatmap.maxCombo
            self.misses = misses

        # Multiple acc values computation
        self.tillerino = tillerino

        # Result
        self.pp = 0
        self.stars = 0
        self.calculate_pp()

    @property
    def unrelaxMods(self):
        return self.mods & ~(mods.RELAX | mods.RELAX2)

    def _calculate_pp(self):
        try:
            # Cache beatmap
            mapFile = mapsHelper.cachedMapPath(self.beatmap.beatmapID)
            mapsHelper.cacheMap(mapFile, self.beatmap)

            # TODO: Sanizite mods

            # Gamemode check
            if self.score is not None and self.score.gameMode != gameModes.CTB:
                raise exceptions.unsupportedGameModeException()

            # Calculate difficulty
            calcBeatmap = CalcBeatmap(mapFile)
            difficulty = Difficulty(beatmap=calcBeatmap, mods=self.unrelaxMods)
            self.stars = difficulty.star_rating

            # Calculate pp
            if self.tillerino:
                results = []
                for acc in (1, 0.99, 0.98, 0.95):
                    results.append(ppCalc.calculate_pp(
                        diff=difficulty,
                        accuracy=acc,
                        combo=self.combo if self.combo >= 0 else calcBeatmap.max_combo,
                        miss=self.misses
                    ))
                self.pp = results
            else:
                # Accuracy check
                if self.accuracy > 1:
                    raise ValueError("Accuracy must be between 0 and 1")
                self.pp = ppCalc.calculate_pp(
                    diff=difficulty,
                    accuracy=self.accuracy,
                    combo=self.combo if self.combo >= 0 else calcBeatmap.max_combo,
                    miss=self.misses
                )
        except exceptions.osuApiFailException:
            log.error("cicciobello ~> osu!api error!")
            self.pp = 0
        except exceptions.unsupportedGameModeException:
            log.error("cicciobello ~> Unsupported gamemode")
            self.pp = 0
        except Exception as e:
            log.error("cicciobello ~> Unhandled exception: {}".format(str(e)))
            self.pp = 0
            raise
        finally:
            log.debug("cicciobello ~> Shutting down, pp = {}".format(self.pp))

    def calculate_pp(self):
        latencyCtx = contextlib.suppress()
        excC = None
        if not self.tillerino:
            latencyCtx = stats["latency"]["classic" if not self.score.isRelax else "relax"].time()
            excC = stats["failures"]["classic" if not self.score.isRelax else "relax"]

        with latencyCtx:
            try:
                return self._calculate_pp()
            finally:
                if not self.tillerino and self.pp == 0 and excC is not None:
                    excC.inc()
