#!/usr/bin/env python3
"""
String Art API Client
Command-line interface for the String Art Flask API
"""

import requests
import argparse
import os
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='String Art API Client')
    parser.add_argument('-i', '--input', required=True, help='Input image file path')
    parser.add_argument('-o', '--output', default='result.png', help='Output file path (default: result.png)')
    parser.add_argument('--server', default='http://localhost:5000', help='API server URL (default: http://localhost:5000)')
    parser.add_argument('--nails', type=int, default=200, help='Number of nails (default: 200)')
    parser.add_argument('-d', '--size', type=int, default=800, help='Output size in pixels (default: 800)')
    parser.add_argument('-s', '--strength', type=float, default=0.1, help='String strength (default: 0.1)')
    parser.add_argument('-l', '--iterations', type=int, default=2000, help='Max iterations (default: 2000)')
    parser.add_argument('-r', '--random-nails', type=int, help='Use random subset of nails')
    parser.add_argument('--shape', choices=['circle', 'rectangle'], default='circle', help='Shape type (default: circle)')
    parser.add_argument('--white-bg', action='store_true', help='Use white background')
    parser.add_argument('--rgb', action='store_true', help='RGB color mode')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)
    
    # Check if input is an image file
    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    if Path(args.input).suffix.lower() not in valid_extensions:
        print(f"Error: '{args.input}' is not a valid image file.")
        print(f"Supported formats: {', '.join(valid_extensions)}")
        sys.exit(1)
    
    if args.verbose:
        print(f"Processing: {args.input}")
        print(f"Server: {args.server}")
        print(f"Parameters:")
        print(f"  - Nails: {args.nails}")
        print(f"  - Size: {args.size}x{args.size}")
        print(f"  - Strength: {args.strength}")
        print(f"  - Iterations: {args.iterations}")
        print(f"  - Shape: {args.shape}")
        print(f"  - White background: {args.white_bg}")
        print(f"  - RGB mode: {args.rgb}")
        if args.random_nails:
            print(f"  - Random nails: {args.random_nails}")
        print()
    
    try:
        # Prepare the request
        with open(args.input, 'rb') as f:
            files = {'image': f}
            data = {
                'total_nails': args.nails,
                'side_len': args.size,
                'export_strength': args.strength,
                'pull_amount': args.iterations,
                'shape_type': args.shape,
                'white_background': 'true' if args.white_bg else 'false',
                'rgb_mode': 'true' if args.rgb else 'false'
            }
            
            if args.random_nails:
                data['random_nails'] = args.random_nails
            
            if args.verbose:
                print("Uploading image and processing... This may take a few minutes.")
            
            # Make the request
            response = requests.post(f"{args.server}/api/process", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                # Download the result
                download_url = f"{args.server}/api/download/{result['output_file']}"
                download_response = requests.get(download_url)
                
                if download_response.status_code == 200:
                    with open(args.output, 'wb') as f:
                        f.write(download_response.content)
                    
                    print(f"✅ Success! String art saved to: {args.output}")
                    print(f"📌 Nails used: {result['nails_count']}")
                    
                    if args.verbose:
                        print(f"🧵 Pull order (first 100): {result['pull_order']}")
                else:
                    print(f"❌ Error downloading result: {download_response.status_code}")
                    sys.exit(1)
            else:
                print(f"❌ Processing error: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        else:
            print(f"❌ API error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Could not connect to {args.server}")
        print("Make sure the Flask server is running.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 