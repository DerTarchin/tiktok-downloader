import sys
import re
import os

def extract_urls(input_files, output_file):
    # Initialize empty list to store URLs and a set to track seen URLs
    all_urls = []
    seen_urls = set()
    
    for input_file in input_files:
        # Resolve to absolute path
        input_file = os.path.abspath(input_file)
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find all URLs using regex
            urls = re.findall(r'https?://[^\s<>"]+', content)
            for url in urls:
                if url not in seen_urls:
                    all_urls.append(url)
                    seen_urls.add(url)
            print(f"Found {len(urls):,} URLs in {input_file}")
            
        except FileNotFoundError:
            print(f"Error: Could not find input file '{input_file}'")
            print(f"Current working directory: {os.getcwd()}")
            print("Please check the file path and try again")
            sys.exit(1)
        except Exception as e:
            print(f"Error processing '{input_file}': {str(e)}")
            sys.exit(1)
    
    # Write combined URLs to output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in all_urls:  # Write URLs in the order they were found
                f.write(f"{url}\n")
        
        print(f"\nSuccessfully extracted {len(all_urls):,} unique URLs to {output_file}")
    except Exception as e:
        print(f"Error writing to output file: {str(e)}")
        sys.exit(1)

def main():
    # Check if input files are provided
    if len(sys.argv) < 2:
        script_name = os.path.basename(__file__)
        print(f"Usage: python {script_name} <input_file1> [input_file2 ...]")
        print("\nExample:")
        print(f"python {script_name} 'My Collection.txt'")
        sys.exit(1)
    
    input_files = sys.argv[1:]
    
    # Use the directory of the first input file for output
    first_file = os.path.abspath(input_files[0])
    input_dir = os.path.dirname(first_file)
    
    # Create output filename
    output_file = os.path.join(input_dir, 'combined_urls.txt')
    
    # Print debug info
    print(f"Script location: {os.path.abspath(__file__)}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Processing files:")
    for f in input_files:
        print(f"  - {os.path.abspath(f)}")
    
    extract_urls(input_files, output_file)

if __name__ == "__main__":
    main() 