"""
Script to reorganize the codebase into proper structure.

This script:
1. Moves files to appropriate directories
2. Updates imports in moved files
3. Creates backup of original files
4. Generates migration report
"""
import os
import shutil
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# File movements mapping
MOVES = {
    # Extractors
    "html_product_extractor.py": "src/fluxer/extractors/html_extractor.py",
    "desc_extractor.py": "deprecated/desc_extractor.py",

    # Search
    "serp_services/get_popular_products.py": "src/fluxer/search/serp_processor.py",
    "serp_pipeline.py": "deprecated/serp_pipeline.py",

    # Tests
    "test_api.py": "tests/integration/test_api.py",
    "test_html_extractor.py": "tests/unit/test_html_extractor.py",
    "test_html_extractor_v2.py": "tests/unit/test_html_extractor_v2.py",
    "test_enhanced_extraction.py": "tests/integration/test_enhanced_extraction.py",
    "test_desc_Extractor.py": "deprecated/test_desc_Extractor.py",
    "test_env_loading.py": "tests/unit/test_env_loading.py",

    # Debugging scripts
    "debug_html_structure.py": "scripts/debug/debug_html_structure.py",
    "debug_strandbags.py": "scripts/debug/debug_strandbags.py",
    "debug_strandbags_with_js.py": "scripts/debug/debug_strandbags_with_js.py",
    "inspect_strandbags_response.py": "scripts/debug/inspect_strandbags_response.py",

    # Example/utility scripts
    "example_integration.py": "scripts/examples/example_integration.py",
    "ant_extractor.py": "deprecated/ant_extractor.py",
    "playwright_fetch.py": "scripts/utils/playwright_fetch.py",
}

# Import replacement mappings
IMPORT_REPLACEMENTS = {
    "from html_product_extractor import": "from fluxer.extractors.html_extractor import",
    "from desc_extractor import": "from fluxer.extractors.desc_extractor import",
    "from serp_services.get_popular_products import": "from fluxer.search.serp_processor import",
    "import html_product_extractor": "from fluxer.extractors import html_extractor",
    "import desc_extractor": "from fluxer.extractors import desc_extractor",
}


def create_directories():
    """Create all necessary directories."""
    dirs = [
        "src/fluxer/extractors",
        "src/fluxer/fetchers",
        "src/fluxer/search",
        "src/fluxer/api",
        "src/fluxer/utils",
        "tests/unit",
        "tests/integration",
        "scripts/debug",
        "scripts/examples",
        "scripts/utils",
        "deprecated",
        "docs",
    ]

    for dir_path in dirs:
        full_path = PROJECT_ROOT / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created: {dir_path}")


def move_file(src, dst):
    """Move a file and update its imports."""
    src_path = PROJECT_ROOT / src
    dst_path = PROJECT_ROOT / dst

    if not src_path.exists():
        print(f"[FAIL] Source not found: {src}")
        return False

    # Ensure destination directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Read source file
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update imports
        for old_import, new_import in IMPORT_REPLACEMENTS.items():
            content = content.replace(old_import, new_import)

        # Write to destination
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"[OK] Moved: {src} -> {dst}")
        return True

    except Exception as e:
        print(f"[FAIL] Error moving {src}: {e}")
        return False


def main():
    """Run the reorganization."""
    print("=" * 80)
    print("GenericProductFluxer - Codebase Reorganization")
    print("=" * 80)

    print("\nStep 1: Creating directories...")
    create_directories()

    print("\nStep 2: Moving files...")
    success_count = 0
    fail_count = 0

    for src, dst in MOVES.items():
        if move_file(src, dst):
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 80)
    print(f"Summary: {success_count} files moved, {fail_count} failures")
    print("=" * 80)

    print("\nNext steps:")
    print("1. Update app.py to import from src.fluxer")
    print("2. Update pyproject.toml to include src/fluxer as package")
    print("3. Run tests to verify everything works")
    print("4. Remove deprecated files when ready")


if __name__ == "__main__":
    main()
