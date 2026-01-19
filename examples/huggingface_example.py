#!/usr/bin/env python3
"""
Example: Download Hugging Face models through Artifact Vault.

This script demonstrates how to use Artifact Vault as a transparent
cache for Hugging Face model downloads.

Prerequisites:
    pip install huggingface-hub transformers

Usage:
    # Start Artifact Vault first
    python main.py --config config-huggingface.yml
    
    # Then run this example
    python examples/huggingface_example.py
"""

import os
import sys

# Configure environment to use Artifact Vault
VAULT_URL = os.environ.get('VAULT_URL', 'http://localhost:8080')
os.environ['HF_ENDPOINT'] = f'{VAULT_URL}/huggingface'

print(f"Using Artifact Vault at: {VAULT_URL}")
print(f"Hugging Face endpoint: {os.environ['HF_ENDPOINT']}")
print("=" * 70)


def example_1_simple_download():
    """Example 1: Simple file download using huggingface_hub."""
    print("\n### Example 1: Simple file download ###\n")
    
    try:
        from huggingface_hub import hf_hub_download
        
        print("Downloading BERT config.json...")
        print("First download will fetch from Hugging Face and cache it.")
        
        # Download a small config file
        path = hf_hub_download(
            repo_id="bert-base-uncased",
            filename="config.json",
            revision="main"
        )
        
        print(f"✓ Downloaded to: {path}")
        
        # Read and display the file
        with open(path, 'r') as f:
            import json
            config = json.load(f)
            print(f"✓ Model type: {config.get('model_type')}")
            print(f"✓ Hidden size: {config.get('hidden_size')}")
        
        print("\nTry running this again - the second download will be instant!")
        
    except ImportError:
        print("⚠ huggingface_hub not installed. Install with: pip install huggingface-hub")
    except Exception as e:
        print(f"✗ Error: {e}")


def example_2_transformers():
    """Example 2: Load model using transformers library."""
    print("\n### Example 2: Load model with transformers ###\n")
    
    try:
        from transformers import AutoConfig, AutoTokenizer
        
        print("Loading DistilBERT configuration...")
        
        # Load model configuration
        config = AutoConfig.from_pretrained("distilbert-base-uncased")
        print(f"✓ Loaded config: {config.model_type}")
        
        print("\nLoading DistilBERT tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        print(f"✓ Loaded tokenizer with vocab size: {tokenizer.vocab_size}")
        
        # Test tokenization
        text = "Hello, Artifact Vault!"
        tokens = tokenizer.tokenize(text)
        print(f"✓ Tokenized '{text}' → {tokens}")
        
        print("\nNote: We only downloaded config/tokenizer, not the full model weights.")
        print("This demonstrates that Artifact Vault caches each file independently.")
        
    except ImportError:
        print("⚠ transformers not installed. Install with: pip install transformers")
    except Exception as e:
        print(f"✗ Error: {e}")


def example_3_direct_requests():
    """Example 3: Direct HTTP requests to Artifact Vault."""
    print("\n### Example 3: Direct HTTP requests ###\n")
    
    try:
        import requests
        
        # Construct URL directly
        url = f"{VAULT_URL}/huggingface/bert-base-uncased/resolve/main/tokenizer_config.json"
        
        print(f"Requesting: {url}")
        
        response = requests.get(url)
        response.raise_for_status()
        
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Content-Type: {response.headers.get('content-type')}")
        print(f"✓ Size: {len(response.content)} bytes")
        
        # Parse and display
        import json
        data = response.json()
        print(f"✓ Tokenizer class: {data.get('tokenizer_class')}")
        
    except ImportError:
        print("⚠ requests not installed. Install with: pip install requests")
    except Exception as e:
        print(f"✗ Error: {e}")


def example_4_dataset():
    """Example 4: Download dataset files."""
    print("\n### Example 4: Download dataset files ###\n")
    
    try:
        from huggingface_hub import hf_hub_download
        
        print("Downloading dataset file...")
        
        # Download a dataset file
        path = hf_hub_download(
            repo_id="squad",
            filename="README.md",
            repo_type="dataset",
            revision="main"
        )
        
        print(f"✓ Downloaded to: {path}")
        
        # Read first few lines
        with open(path, 'r') as f:
            lines = f.readlines()[:5]
            print("\n✓ First 5 lines of README:")
            for line in lines:
                print(f"  {line.rstrip()}")
        
    except ImportError:
        print("⚠ huggingface_hub not installed. Install with: pip install huggingface-hub")
    except Exception as e:
        print(f"✗ Error: {e}")


def check_vault_connection():
    """Check if Artifact Vault is running."""
    import requests
    
    try:
        response = requests.get(VAULT_URL, timeout=5)
        print(f"✓ Artifact Vault is running at {VAULT_URL}\n")
        return True
    except requests.RequestException as e:
        print(f"✗ Cannot connect to Artifact Vault at {VAULT_URL}")
        print(f"  Error: {e}")
        print("\nPlease start Artifact Vault first:")
        print("  python main.py --config config-huggingface.yml")
        return False


def main():
    print("Hugging Face + Artifact Vault Examples")
    print("=" * 70)
    
    # Check connection
    if not check_vault_connection():
        sys.exit(1)
    
    # Run examples
    example_1_simple_download()
    example_2_transformers()
    example_3_direct_requests()
    example_4_dataset()
    
    print("\n" + "=" * 70)
    print("All examples completed!")
    print("\nNext steps:")
    print("  - Check cache contents: ls -lh /tmp/artifact_cache/huggingface/")
    print("  - View Artifact Vault logs to see redirect handling")
    print("  - Try downloading larger model files")


if __name__ == '__main__':
    main()
