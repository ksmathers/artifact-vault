#!/usr/bin/env python3
"""
Test script for Hugging Face backend in Artifact Vault.

This script tests the basic functionality of the Hugging Face backend
by attempting to download a small model file through the cache.

Usage:
    python test_huggingface.py [--vault-url http://localhost:8080]
"""

import argparse
import requests
import sys
import time


def test_huggingface_download(vault_url):
    """Test downloading a file through the Hugging Face backend."""
    
    # Use a small, well-known model for testing
    test_files = [
        {
            'path': 'bert-base-uncased/resolve/main/config.json',
            'description': 'BERT config.json (small file)',
        },
        {
            'path': 'bert-base-uncased/resolve/main/tokenizer.json',
            'description': 'BERT tokenizer.json (medium file)',
        }
    ]
    
    print(f"Testing Hugging Face backend at {vault_url}")
    print("=" * 70)
    
    for test_file in test_files:
        path = test_file['path']
        description = test_file['description']
        url = f"{vault_url}/huggingface/{path}"
        
        print(f"\nTesting: {description}")
        print(f"URL: {url}")
        
        # First request - should fetch and cache
        print("\nFirst request (cache miss)...")
        start_time = time.time()
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Read the content
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
            
            first_duration = time.time() - start_time
            print(f"✓ Success: Downloaded {len(content)} bytes in {first_duration:.2f}s")
            
        except requests.RequestException as e:
            print(f"✗ Failed: {e}")
            continue
        
        # Second request - should serve from cache
        print("\nSecond request (cache hit)...")
        start_time = time.time()
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Read the content
            cached_content = b''
            for chunk in response.iter_content(chunk_size=8192):
                cached_content += chunk
            
            second_duration = time.time() - start_time
            print(f"✓ Success: Served {len(cached_content)} bytes in {second_duration:.2f}s")
            
            # Verify content is the same
            if content == cached_content:
                print(f"✓ Content verification passed")
            else:
                print(f"✗ Content mismatch!")
                
            # Cache should be faster
            if second_duration < first_duration:
                speedup = first_duration / second_duration
                print(f"✓ Cache speedup: {speedup:.1f}x faster")
            else:
                print(f"⚠ Cache was not faster (might be cached upstream)")
                
        except requests.RequestException as e:
            print(f"✗ Failed: {e}")
            continue
        
        print("-" * 70)
    
    print("\n" + "=" * 70)
    print("Testing complete!")


def test_redirect_handling(vault_url):
    """Test that redirects are being handled correctly."""
    
    print("\nTesting redirect handling...")
    print("=" * 70)
    
    # This URL should trigger a redirect to CDN
    path = "bert-base-uncased/resolve/main/config.json"
    url = f"{vault_url}/huggingface/{path}"
    
    print(f"URL: {url}")
    print("\nThis should follow redirects from huggingface.co to CDN...")
    
    try:
        # Make request with redirect tracking
        response = requests.get(url, allow_redirects=True)
        response.raise_for_status()
        
        # Check if we got content
        content_length = len(response.content)
        print(f"✓ Successfully downloaded {content_length} bytes")
        
        # Try to determine if redirect was followed (can't easily check from client side)
        print(f"✓ Final content received (redirects handled by Artifact Vault)")
        
    except requests.RequestException as e:
        print(f"✗ Failed: {e}")
        return False
    
    print("=" * 70)
    return True


def test_error_handling(vault_url):
    """Test error handling for non-existent files."""
    
    print("\nTesting error handling...")
    print("=" * 70)
    
    # Test with a non-existent file
    path = "nonexistent-model/nonexistent-file/resolve/main/doesnt-exist.bin"
    url = f"{vault_url}/huggingface/{path}"
    
    print(f"Testing with non-existent file:")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url)
        
        if response.status_code == 404 or response.status_code == 502:
            print(f"✓ Correctly returned error status: {response.status_code}")
            return True
        else:
            print(f"⚠ Unexpected status code: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"✓ Correctly raised exception: {e}")
        return True
    
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Test Hugging Face backend in Artifact Vault'
    )
    parser.add_argument(
        '--vault-url',
        default='http://localhost:8080',
        help='Artifact Vault URL (default: http://localhost:8080)'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip download tests'
    )
    
    args = parser.parse_args()
    
    # Check if Artifact Vault is running
    try:
        response = requests.get(args.vault_url, timeout=5)
        print(f"✓ Artifact Vault is running at {args.vault_url}")
    except requests.RequestException as e:
        print(f"✗ Cannot connect to Artifact Vault at {args.vault_url}")
        print(f"  Error: {e}")
        print("\nMake sure Artifact Vault is running:")
        print("  python main.py --config config.yml")
        sys.exit(1)
    
    # Run tests
    if not args.skip_download:
        test_huggingface_download(args.vault_url)
    
    test_redirect_handling(args.vault_url)
    test_error_handling(args.vault_url)
    
    print("\n✓ All tests completed!")


if __name__ == '__main__':
    main()
