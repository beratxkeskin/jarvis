import os
import glob
import datetime
from pathlib import Path
import re

# Base path for storing smart notes
NOTES_DIR = Path(__file__).parent.parent / "memory" / "smart_notes"

def _ensure_dir():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

def create_note(content: str, category: str = "general", tags: list[str] = None, deadline: str = None, priority: str = "normal") -> str:
    _ensure_dir()
    if not tags:
        tags = []
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    note_id = f"note_{timestamp}"
    file_path = NOTES_DIR / f"{note_id}.md"
    
    # Format tags for YAML
    tags_str = ", ".join([f'"{t}"' for t in tags])
    
    yaml_frontmatter = f"""---
id: {note_id}
category: {category}
tags: [{tags_str}]
deadline: {deadline or "None"}
priority: {priority}
created_at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
---
"""
    
    note_content = f"{yaml_frontmatter}\n# Note\n\n{content}\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(note_content)
        
    return note_id

def parse_note(file_path: Path) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse YAML frontmatter roughly
        frontmatter_match = re.search(r"^---\s*(.*?)\s*---", content, re.DOTALL)
        metadata = {}
        body = content
        
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            body = content[frontmatter_match.end():].strip()
            
            for line in frontmatter.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    metadata[key.strip()] = val.strip()
                    
        return {
            "id": file_path.stem,
            "metadata": metadata,
            "body": body,
            "file_path": str(file_path)
        }
    except Exception as e:
        return {"id": file_path.stem, "error": str(e)}

def list_notes() -> list[dict]:
    _ensure_dir()
    notes = []
    for md_file in NOTES_DIR.glob("*.md"):
        notes.append(parse_note(md_file))
    # Sort by created_at descending (newest first) based on filename
    notes.sort(key=lambda x: x.get("id", ""), reverse=True)
    return notes

def search_notes(query: str = None, category: str = None) -> list[dict]:
    all_notes = list_notes()
    results = []
    
    for note in all_notes:
        if "error" in note:
            continue
            
        match = True
        if category and category.lower() != "all":
            note_cat = note.get("metadata", {}).get("category", "").lower()
            if category.lower() not in note_cat:
                match = False
                
        if query:
            q = query.lower()
            body_text = note.get("body", "").lower()
            tags_text = note.get("metadata", {}).get("tags", "").lower()
            if q not in body_text and q not in tags_text:
                match = False
                
        if match:
            results.append(note)
            
    return results

def delete_note(note_id: str) -> bool:
    _ensure_dir()
    file_path = NOTES_DIR / f"{note_id}.md"
    if file_path.exists():
        file_path.unlink()
        return True
    return False
