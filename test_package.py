#!/usr/bin/env python3
"""Simple test to verify the package works correctly."""

import sys
from pathlib import Path

def test_imports():
    """Test that all imports work correctly."""
    try:
        import meeting_notes_handler
        print(f"✅ Package version: {meeting_notes_handler.__version__}")
        
        from meeting_notes_handler import Config, GoogleMeetFetcher, FileOrganizer, DocsConverter
        print("✅ All imports successful")
        
        # Test config creation
        config = Config()
        print(f"✅ Config created successfully")
        print(f"   Output directory: {config.output_directory}")
        print(f"   Default days back: {config.days_back}")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_cli_entry_point():
    """Test that CLI entry point exists."""
    try:
        from meeting_notes_handler.main import cli
        print("✅ CLI entry point accessible")
        return True
    except Exception as e:
        print(f"❌ CLI entry point failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Meeting Notes Handler package...")
    print()
    
    success = True
    success &= test_imports()
    success &= test_cli_entry_point()
    
    print()
    if success:
        print("🎉 All tests passed! Package is ready.")
        sys.exit(0)
    else:
        print("❌ Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()