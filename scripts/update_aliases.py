#!/usr/bin/env python3
"""Script to update TikTok Downloader aliases in ~/.zshrc file."""

import os
import re
import sys

def get_project_root():
    """Get the absolute path to the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_aliases(project_root):
    """Generate the alias definitions using the project root path."""
    aliases = {
        'tt': 'main.py',
        'ttdedupe': 'scripts/dedupe_links.py',
        'ttfix': 'scripts/fix_issues.py',
        'ttparse': 'scripts/parse_urls.py',
        'ttgroupdedupe': 'scripts/remove_group_duplicates.py',
        'ttcount': 'scripts/count_videos_to_download.py',
        'ttcollection': 'scripts/fetch_collection_videos.py',
        'ttcollect': 'scripts/fetch_user_collections.py',
        'ttsplit': 'scripts/split_links.py',
        'ttaudio': 'scripts/download_tiktok_audio.py',
        'ttsync': 'scripts/sync_to_remote.py',
        'ttphotos': 'scripts/download_slideshows.py'
    }
    
    alias_lines = []
    for alias_name, script_path in aliases.items():
        full_path = os.path.join(project_root, script_path)
        alias_lines.append(f'alias {alias_name}="python3 {full_path}"')
    
    # Add help alias that shows all available commands with their script names
    alias_help_lines = [f'{name} ({script})' for name, script in sorted(aliases.items())]
    alias_help_text = '\\n'.join(alias_help_lines)
    alias_lines.append(f'alias tthelp="echo -e \'{alias_help_text}\'"')
    
    return alias_lines

def clean_zshrc_content(content):
    """Remove any existing TikTok Downloader aliases from the content."""
    # Remove section with marker
    pattern = r'# TikTok Downloader aliases\n(?:alias tt.*\n)*\n?'
    content = re.sub(pattern, '', content)
    
    # Remove individual tt aliases that might exist elsewhere
    lines = content.splitlines()
    cleaned_lines = [line for line in lines if not line.strip().startswith('alias tt')]
    
    # Ensure proper spacing
    content = '\n'.join(cleaned_lines)
    while '\n\n\n' in content:
        content = content.replace('\n\n\n', '\n\n')
    return content

def update_zshrc():
    """Update the ~/.zshrc file with TikTok Downloader aliases."""
    project_root = get_project_root()
    zshrc_path = os.path.expanduser('~/.zshrc')
    
    try:
        # Read existing .zshrc content
        with open(zshrc_path, 'r') as f:
            content = f.read()
        
        # Clean existing content
        content = clean_zshrc_content(content)
        
        # Generate new aliases
        new_aliases = generate_aliases(project_root)
        alias_block = '\n'.join(['# TikTok Downloader aliases'] + new_aliases + [''])
        
        # Add new aliases at the end
        if not content.endswith('\n'):
            content += '\n'
        content += '\n' + alias_block
        
        # Write updated content back
        with open(zshrc_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Successfully updated aliases in {zshrc_path}")
        print("✓ Run 'source ~/.zshrc' to apply changes")
        
    except Exception as e:
        print(f"Error updating {zshrc_path}: {e}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(update_zshrc()) 