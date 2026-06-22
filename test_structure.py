#!/usr/bin/env python3
"""
Test script to verify project structure and basic functionality
"""

import os
import sys

def test_project_structure():
    """Test that all required files exist"""
    print("Testing Stock Screener Project Structure")
    print("=" * 50)

    required_files = [
        'app.py',
        'data_fetcher.py',
        'screener.py',
        'ticker_universe.py',
        'requirements.txt',
        '.gitignore',
        'README.md'
    ]

    all_exist = True
    for file in required_files:
        exists = os.path.exists(file)
        status = "✓" if exists else "✗"
        print(f"{status} {file:<25} {'Found' if exists else 'Missing'}")
        if not exists:
            all_exist = False

    print("\n" + "=" * 50)

    if all_exist:
        print("✅ All required files are present!")
    else:
        print("❌ Some files are missing!")
        return False

    # Test imports (without external dependencies)
    print("\nTesting module imports (without external dependencies)...")
    try:
        # Test ticker_universe module
        import ticker_universe
        tickers = ticker_universe.get_full_universe()
        print(f"✓ ticker_universe module: {len(tickers)} tickers loaded")

        # Verify reasonable number of tickers
        assert 400 <= len(tickers) <= 1000, f"Unexpected number of tickers: {len(tickers)}"
        print(f"✓ Ticker count validation passed")

        # Test sector ETFs
        etfs = ticker_universe.get_sector_etfs()
        print(f"✓ Sector ETFs: {len(etfs)} sectors defined")

    except Exception as e:
        print(f"✗ Error testing modules: {e}")
        return False

    print("\n" + "=" * 50)
    print("✅ Project structure test completed successfully!")
    print("\nNext steps:")
    print("1. Create a virtual environment: python3 -m venv venv")
    print("2. Activate it: source venv/bin/activate")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Run the app: streamlit run app.py")

    return True

def check_requirements():
    """Check requirements.txt content"""
    print("\nChecking requirements.txt...")
    print("-" * 30)

    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read().strip().split('\n')

        print("Required packages:")
        for req in requirements:
            print(f"  • {req}")

        expected_packages = ['streamlit', 'yfinance', 'pandas', 'numpy', 'requests']
        found_packages = [pkg.split('==')[0] for pkg in requirements]

        for pkg in expected_packages:
            if pkg in found_packages:
                print(f"✓ {pkg} is listed")
            else:
                print(f"✗ {pkg} is missing from requirements")

    except Exception as e:
        print(f"✗ Error reading requirements.txt: {e}")
        return False

    return True

def main():
    """Run all tests"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    success = test_project_structure()
    success = check_requirements() and success

    if success:
        print("\n" + "🎉" * 20)
        print("🚀 Stock Screener project is ready to go!")
        print("🎉" * 20)
    else:
        print("\n⚠️  Please fix the issues above before proceeding.")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())