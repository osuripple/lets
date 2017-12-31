## LETS [![Code Health](https://landscape.io/github/osuripple/lets/master/landscape.svg?style=flat)](https://landscape.io/github/osuripple/lets/master)

- Origin: https://zxq.co/ripple/lets
- Mirror: https://github.com/osuripple/lets

## Latest Essential Tatoe Server
This server handles every non real time client feature, so:
- Ingame scoreboards
- Score submission
- Screenshots
- Replays
- osu!direct, thanks to [cheesegull](https://github.com/osuripple/cheesegull)
- Tillerino-like API (partially broken)
- osu!standard and taiko pp calculation with [oppai-ng](https://github.com/francesco149/oppai-ng), made by Franc[e]sco
- osu!mania pp calculation with `wifipiano2`, made by Nyo with reference code from [Tom94's osu-performance](https://github.com/ppy/osu-performance)
- catch the beat pp calculation with [catch-the-pp](https://github.com/osuripple/catch-the-pp), made by Sunpy and cythonized by Nyo

## Requirements
- Python 3.5+
- Cython
- C compiler

## How to set up LETS
First of all, initialize and update the submodules
```
$ git submodule init && git submodule update
```
afterwards, install the required dependencies with pip
```
$ pip install -r requirements.txt
```
compile all `*.pyx` files to `*.so` or `*.dll` files using `setup.py` (distutils file).
This compiles `catch-the-pp` as well.
```
$ python3 setup.py build_ext --inplace
```
then, run LETS once to create the default config file and edit it
```
$ python3 lets.py
$ nano config.ini
```
finally, compile oppai-ng (inside pp/oppai-ng).

## tomejerry.py
`tomejerry.py` is a tool that allows you to calculate pp for specific scores. It's extremely useful to do mass PP recalculations if you mess something up. It uses lets' config and packages, so make sure lets is installed and configured correctly before using it.  
`tomejerry` supports a lot of parameters, the main ones are:  
- `-r`, to recalculate PP for every score on every game mode
- `-z` to calculate PP for scores with 0 pp  
- `-g x` to recalculate PP for scores for `x` gamemode (0: std, 1: taiko, 2: ctb, 3: mania)
- `-i x` to recalculate PP for score with `x` id  
- `-n x` to recalculate PP for scores submitted by user with `x` username  
For a full list of all the arguments supported by `tomejerry`, run `python3 tomejerry.py --help`

## License
This project is licensed under the GNU AGPL 3 License.  
See the "LICENSE" file for more information.  
This project contains code taken by reference from [osu-performance](https://github.com/ppy/osu-performance) by Tom94.
