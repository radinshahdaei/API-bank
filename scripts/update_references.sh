#!/usr/bin/env bash
# Update all reference API repos from init.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REFS_DIR="$SCRIPT_DIR/../references"

mkdir -p "$REFS_DIR"

clone_or_pull() {
    local name="$1"
    local url="$2"

    if [ -d "$REFS_DIR/$name/.git" ]; then
        echo "📥 Pulling $name..."
        git -C "$REFS_DIR/$name" pull --ff-only
    else
        echo "📥 Cloning $name..."
        git clone --depth 1 "$url" "$REFS_DIR/$name"
    fi
}

echo "Updating reference API repositories..."
echo "========================================"

clone_or_pull "free-llm-api-resources"   "https://github.com/cheahjs/free-llm-api-resources.git"
clone_or_pull "awesome-free-llm-apis"    "https://github.com/mnfst/awesome-free-llm-apis.git"
clone_or_pull "awesome-free-models"      "https://github.com/12britz/awesome-free-models.git"
clone_or_pull "public-apis"              "https://github.com/public-apis/public-apis.git"

echo ""
echo "✅ All reference repos up to date."
echo "   $REFS_DIR/"
ls -d "$REFS_DIR"/*/ 2>/dev/null | while read d; do
    echo "   ├── $(basename "$d")/"
done
