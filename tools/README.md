# Local test tools

`engine.py` and `random_bot.py` are unmodified copies of the official starter
kit:

- `/home/leo/Documents/Poker/Starter_Kit/engine.py`
- `/home/leo/Documents/Poker/Starter_Kit/example_bots/random_bot.py`

They are kept here so local matches can be reproduced from this repository.
They are not part of the submission and should not be edited.

Run a match:

```sh
python3.11 tools/engine.py bot.py tools/random_bot.py --hands 400 --seed 173000
```

If the interpreter used by the engine does not have NumPy, pass the correct one:

```sh
python3.11 tools/engine.py bot.py tools/random_bot.py \
  --hands 400 --seed 173000 --python /path/to/python
```

Use `--stage 2` for the 1,000-hand stage and `--log-dir ""` to disable logs.
