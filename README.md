# LETS
## Latest Essential Tatoe Server
### aka ripple's new score server
This server handles every non-real time client feature, so:
- Ingame scoreboards
- Score submission (and PP calculation)
- Screenshots
- Replays
- osu!direct
- Tillerino-like API

## Requirements
- Python 3.5
- MySQLdb (`pip install mysqlclient` or `pip install mysql-python`)
- Tornado (`pip install tornado`)
- Bcrypt (`pip install bcrypt`)
- oppai

## How to set up LETS
First of all, install all the dependencies
```
$ pip install mysqlclient
$ pip install tornado
$ pip install bcrypt
```
then, run LETS once to create the default config file and edit it
```
$ python3 lets.py
$ nano lets.py
```
finally, configure oppai as described below

## How to set up oppai with LETS
LETS uses lolisamurai's oppai as pp calculator. We use a slightly modified version of oppai, you can find it [here](https://github.com/osuripple/oppai).  
Go one directory above LETS (in the same directory where you have old-frontend, pep.py, lets and so on) and clone `oppai` inside the `oppai` folder, compile it with `make` and create the `maps` folder
```
path/to/ripple$ git clone https://github.com/osuripple/oppai.git
path/to/ripple$ cd oppai
path/to/ripple/oppai$ make
path/to/ripple/oppai$ mkdir maps
```
the interface between `oppai` and LETS is `rippoppai.py`. You can use that also to calculate pp for specific scores, run `python3 rippoppai.py --help` for more info.

## License

```
Copyright (C) The Ripple Developers - All Rights Reserved
Unauthorized copying of this file, via any medium is strictly prohibited
Proprietary and confidential
```
