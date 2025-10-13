@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === Cesty ===
set JENA_HOME=C:\Programy\apache-jena-5.5.0\apache-jena-5.5.0
set DATASETS=C:\Users\Jana\GitHub\PhD\RDF_generator\datasets
set OUTFILE=C:\Users\Jana\GitHub\PhD\RDF_generator\jena-benchmark.csv

REM === Skip list (soubory, které chceme přeskočit) ===
set skip_files=notation3_10.n3 notation3_100.n3 notation3_1000.n3 notation3_5000.n3

echo file,syntax,jena_parse_s,jena_serialize_s > "%OUTFILE%"

for %%f in ("%DATASETS%\*.ttl" "%DATASETS%\*.trig" "%DATASETS%\*.nq" "%DATASETS%\*.nt") do (
    echo %skip_files% | findstr /i "\<%%~nxf\>" >nul
    if errorlevel 1 (
        set "syntax="
        if /i "%%~xf"==".ttl"  set "syntax=turtle"
        if /i "%%~xf"==".trig" set "syntax=trig"
        if /i "%%~xf"==".nq"   set "syntax=nquads"
        if /i "%%~xf"==".nt"   set "syntax=nt"

        echo Testing %%~nxf with syntax=!syntax!

        REM --- Parse only ---
        for /f "tokens=3 delims= " %%t in ('"%JENA_HOME%\bat\riot.bat" --time --count --sink --syntax=!syntax! %%f 2^>^&1') do (
            set parse_time=%%t
        )

        REM --- nahradit čárku tečkou ---
        set parse_time=!parse_time:,=.!

        echo %%~nxf,!syntax!,!parse_time!,!serialize_time!>> "%OUTFILE%"
    ) else (
        echo Skipping %%~nxf
    )
)

echo Done! Results saved to %OUTFILE%
pause
