#!/usr/bin/env bash
# ──────────────────────────────────────────────
# lumina-proto — compile .proto → Python + C++ stubs
# Linux/macOS equivalent of build_proto.bat
# ──────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="${PROJECT_DIR}/lumina-proto/src"
BUILD_DIR="${PROJECT_DIR}/lumina-proto/build"
PROTO_FILE="${PROTO_DIR}/lumina.proto"

echo "[lumina-proto] Compiling ${PROTO_FILE} ..."
mkdir -p "${BUILD_DIR}"

# Python stubs
echo "[lumina-proto] Generating Python code ..."
python -m grpc_tools.protoc \
    -I "${PROTO_DIR}" \
    --python_out="${BUILD_DIR}" \
    --grpc_python_out="${BUILD_DIR}" \
    "${PROTO_FILE}"
echo "[lumina-proto] Python stubs -> ${BUILD_DIR}"

# Fix Python import paths
sed -i 's/import lumina_pb2/from . import lumina_pb2/' "${BUILD_DIR}/lumina_pb2_grpc.py"

# C++ stubs (if protoc with gRPC plugin is available)
if command -v protoc &>/dev/null; then
    GRPC_CPP_PLUGIN="${GRPC_CPP_PLUGIN:-$(command -v grpc_cpp_plugin)}"
    if [ -n "${GRPC_CPP_PLUGIN}" ] || [ -x "${GRPC_CPP_PLUGIN}" ]; then
        echo "[lumina-proto] Generating C++ code ..."
        protoc \
            -I "${PROTO_DIR}" \
            --cpp_out="${BUILD_DIR}" \
            --grpc_out="${BUILD_DIR}" \
            --plugin=protoc-gen-grpc="${GRPC_CPP_PLUGIN}" \
            "${PROTO_FILE}"
        echo "[lumina-proto] C++ stubs -> ${BUILD_DIR}"
    else
        echo "[lumina-proto] grpc_cpp_plugin not found, skipping C++ stubs"
    fi
else
    echo "[lumina-proto] protoc not found, skipping C++ stubs"
fi

echo "[lumina-proto] Build complete."
