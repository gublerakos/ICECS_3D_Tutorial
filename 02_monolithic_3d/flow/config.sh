#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
export VARIANTS="2d_dual 2d_quad 3d_dual 3d_quad"
export PYTHONDONTWRITEBYTECODE=1
