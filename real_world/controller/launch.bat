@echo off
rem Windows: double-click to open the controller in Chrome or Edge (Web Serial talks to the IR bridge over USB).
cd /d "%~dp0"
set PORT=8765
set URL=http://localhost:%PORT%/index.html
set BROWSER=
for %%B in ("%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%LocalAppData%\Google\Chrome\Application\chrome.exe" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe") do (
  if not defined BROWSER if exist %%B set BROWSER=%%B
)
if not defined BROWSER (
  echo Web Serial needs Google Chrome or Microsoft Edge. Install Chrome: https://www.google.com/chrome/
  pause
  exit /b 1
)
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY ( where python >nul 2>nul && set PY=python )
if defined PY (
  start "RoboBuilder controller server" /min %PY% -m http.server %PORT% --bind 127.0.0.1
  timeout /t 2 /nobreak >nul
  start "" %BROWSER% "%URL%"
  echo RoboBuilder controller: %URL%
  echo Close the minimised "RoboBuilder controller server" window when you are done.
) else (
  start "" %BROWSER% "%~dp0index.html"
  echo Opened index.html. Chrome and Edge allow Web Serial on a local file.
)
timeout /t 5 >nul
