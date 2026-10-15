#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
export TOP_AREA_SCALE="${TOP_AREA_SCALE:-1.0}"
export MAX_IMBALANCE="${MAX_IMBALANCE:-0.02}"
export TOP_LIBERTY="${TOP_LIBERTY:-$ROOT/pdk/nangate_typical_top_tier.lib}"
export BOTTOM_LIBERTY="${BOTTOM_LIBERTY:-$ROOT/pdk/nangate15_original.lib}"
export TOP_LEF="${TOP_LEF:-$ROOT/pdk/nangate_stdcell_top_tier.lef}"
export BOTTOM_LEF="${BOTTOM_LEF:-$ROOT/pdk/nangate_stdcell_bottom_tier.lef}"
export PYTHONDONTWRITEBYTECODE=1
