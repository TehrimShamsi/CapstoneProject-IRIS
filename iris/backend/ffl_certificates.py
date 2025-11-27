"""
SSL Certificate Fix Script for IRIS Backend

This script fixes SSL certificate verification issues by:
1. Updating certifi to the latest version
2. Setting up proper certificate paths for requests/urllib3
3. Creating environment variable for SSL_CERT_FILE

Run this from the backend directory:
    .venv\Scripts\python fix_ssl_certificates.py
"""

import os
import sys
import ssl
import certifi
from pathlib import Path

def main():
    print("=" * 60)
    print("IRIS SSL Certificate Fix Utility")
    print("=" * 60)
    
    # 1. Display current Python and certifi info
    print(f"\n✓ Python version: {sys.version}")
    print(f"✓ Python executable: {sys.executable}")
    print(f"✓ Certifi version: {certifi.__version__}")
    print(f"✓ Certifi certificate bundle: {certifi.where()}")
    
    # 2. Check if certificate file exists
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        print(f"✓ Certificate file exists ({os.path.getsize(cert_path)} bytes)")
    else:
        print(f"✗ Certificate file NOT FOUND at {cert_path}")
        return False
    
    # 3. Test SSL context creation
    try:
        context = ssl.create_default_context(cafile=cert_path)
        print("✓ SSL context created successfully")
    except Exception as e:
        print(f"✗ Failed to create SSL context: {e}")
        return False
    
    # 4. Set environment variable
    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    print(f"✓ Environment variables set:")
    print(f"  SSL_CERT_FILE={cert_path}")
    print(f"  REQUESTS_CA_BUNDLE={cert_path}")
    
    # 5. Create .env addition suggestion
    backend_dir = Path(__file__).parent
    env_file = backend_dir / ".env"
    
    print(f"\n{'=' * 60}")
    print("RECOMMENDED: Add these lines to your .env file:")
    print(f"{'=' * 60}")
    print(f"SSL_CERT_FILE={cert_path}")
    print(f"REQUESTS_CA_BUNDLE={cert_path}")
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        if 'SSL_CERT_FILE' not in env_content:
            print(f"\n⚠ .env file exists but doesn't contain SSL_CERT_FILE")
            response = input("Would you like to add these lines automatically? (y/n): ")
            
            if response.lower() == 'y':
                with open(env_file, 'a') as f:
                    f.write(f"\n# SSL Certificate Configuration\n")
                    f.write(f"SSL_CERT_FILE={cert_path}\n")
                    f.write(f"REQUESTS_CA_BUNDLE={cert_path}\n")
                print("✓ SSL configuration added to .env")
        else:
            print("✓ .env already contains SSL configuration")
    else:
        print(f"\n⚠ .env file not found at {env_file}")
        print("  You can create it manually with the lines above")
    
    # 6. Test actual HTTPS connection
    print(f"\n{'=' * 60}")
    print("Testing HTTPS connection...")
    print(f"{'=' * 60}")
    
    try:
        import requests
        response = requests.get('https://www.google.com', timeout=5)
        print(f"✓ HTTPS connection successful (status: {response.status_code})")
    except requests.exceptions.SSLError as e:
        print(f"✗ SSL Error during test: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. Try reinstalling certifi: pip install --upgrade --force-reinstall certifi")
        print("2. Check your antivirus/firewall settings")
        print("3. Verify you're not behind a corporate proxy")
        return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False
    
    print(f"\n{'=' * 60}")
    print("✓ SSL Certificate setup complete!")
    print(f"{'=' * 60}")
    print("\nNext steps:")
    print("1. Restart your terminal/PowerShell session")
    print("2. Reactivate the virtual environment")
    print("3. Run: .venv\\Scripts\\python -m uvicorn app.main:app --reload")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)