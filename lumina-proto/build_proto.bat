@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set PROTO_DIR=%~dp0src
set BUILD_DIR=%~dp0build
set PROTO_FILE=%PROTO_DIR%\lumina.proto

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

echo [lumina-proto] Compiling lumina.proto ...

:: --- C++ stubs ---
echo [lumina-proto] Generating C++ code ...
protoc -I "%PROTO_DIR%" --cpp_out="%BUILD_DIR%" --grpc_out="%BUILD_DIR%" ^
    --plugin=protoc-gen-grpc="%GRPC_CPP_PLUGIN%" "%PROTO_FILE%"
if %ERRORLEVEL% neq 0 (
    echo [lumina-proto] [ERROR] C++ code generation failed.
    exit /b %ERRORLEVEL%
)
echo [lumina-proto] C++ stubs generated in %BUILD_DIR%

:: --- Python stubs ---
echo [lumina-proto] Generating Python code ...
python -m grpc_tools.protoc -I "%PROTO_DIR%" --python_out="%BUILD_DIR%" ^
    --grpc_python_out="%BUILD_DIR%" "%PROTO_FILE%"
if %ERRORLEVEL% neq 0 (
    echo [lumina-proto] [ERROR] Python code generation failed.
    exit /b %ERRORLEVEL%
)
echo [lumina-proto] Python stubs generated in %BUILD_DIR%

:: --- Fix Python imports (proto module path) ---
set GEN_PROTO=%BUILD_DIR%\lumina_pb2.py
if exist "%GEN_PROTO%" (
    echo [lumina-proto] Fixing Python import paths ...
    set "SEARCH=import lumina_pb2"
    set "REPLACE=from . import lumina_pb2"
    powershell -Command "(gc '%GEN_PROTO%') -replace 'import lumina_pb2', 'from . import lumina_pb2' | Set-Content '%GEN_PROTO%'"
    powershell -Command "(gc '%BUILD_DIR%\lumina_pb2_grpc.py') -replace 'import lumina_pb2', 'from . import lumina_pb2' | Set-Content '%BUILD_DIR%\lumina_pb2_grpc.py'"
)

echo [lumina-proto] Build complete.
exit /b 0
