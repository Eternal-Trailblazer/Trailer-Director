@echo off
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%src"
python "%ROOT%run.py" %*