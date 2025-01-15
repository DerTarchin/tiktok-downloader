#!/usr/bin/env python3

import os
import math
import argparse

def split_file(input_file, max_lines=500):
    """
    Split a file into multiple parts with max_lines per file.
    
    Args:
        input_file (str): Path to the input file
        max_lines (int): Maximum number of lines per output file
    """
    # Read all lines from input file
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Calculate number of parts needed
    total_lines = len(lines)
    num_parts = math.ceil(total_lines / max_lines)
    
    # Get base filename without extension
    base_name = os.path.splitext(input_file)[0]
    extension = os.path.splitext(input_file)[1]
    
    # Split and write files
    for i in range(num_parts):
        start_idx = i * max_lines
        end_idx = min((i + 1) * max_lines, total_lines)
        
        # Create output filename with part number
        output_file = f"{base_name} (Part {i + 1}){extension}"
        
        # Write lines to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(lines[start_idx:end_idx])
        
        print(f"Created {output_file} with {end_idx - start_idx} lines")

def main():
    parser = argparse.ArgumentParser(description='Split a file into multiple parts with maximum lines per file')
    parser.add_argument('input_file', help='Input file to split')
    parser.add_argument('--max-lines', type=int, default=500, help='Maximum lines per output file (default: 500)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist")
        return
    
    split_file(args.input_file, args.max_lines)

if __name__ == '__main__':
    main() 