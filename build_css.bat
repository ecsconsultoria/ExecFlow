@echo off
REM Rebuild Tailwind CSS (minified, production build)
cd /d "%~dp0"
tools\tailwindcss.exe -c tailwind.config.js -i app\static\css\tailwind.src.css -o app\static\css\tailwind.css --minify
