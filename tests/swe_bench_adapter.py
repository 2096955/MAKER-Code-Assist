#!/usr/bin/env python3
"""
SWE-bench Adapter: Converts between MAKER output and SWE-bench patch format

Handles:
- Parsing MAKER code generation output
- Converting file edits to unified diff format
- Extracting patches from markdown code blocks
- Validating patch format
"""

import re
import difflib
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class PatchAdapter:
    """Converts MAKER output to unified diff patches"""

    @staticmethod
    def extract_patch_from_maker_output(maker_output: str) -> str:
        """
        Extract unified diff from MAKER output
        MAKER can output in several formats:
        1. Direct unified diff (preferred)
        2. Markdown code blocks with file contents
        3. File path + content pairs
        4. JSON with file_path and new_content
        """
        # Format 1: Direct unified diff
        if 'diff --git' in maker_output:
            return PatchAdapter._extract_unified_diff(maker_output)

        # Format 2: Markdown code blocks
        if '```' in maker_output:
            return PatchAdapter._convert_markdown_to_diff(maker_output)

        # Format 3: JSON format
        if maker_output.strip().startswith('{'):
            return PatchAdapter._convert_json_to_diff(maker_output)

        # Format 4: Plain code (assume single file)
        return PatchAdapter._convert_plain_code_to_diff(maker_output)

    @staticmethod
    def _extract_unified_diff(text: str) -> str:
        """Extract existing unified diff from text"""
        lines = text.split('\n')
        diff_lines = []
        in_diff = False

        for line in lines:
            if line.startswith('diff --git'):
                in_diff = True
            if in_diff:
                diff_lines.append(line)
                # Check if we've reached end of diff
                if line.startswith('diff --git') and diff_lines:
                    if len(diff_lines) > 1:  # New diff starting, but keep it
                        pass

        return '\n'.join(diff_lines)

    @staticmethod
    def _convert_markdown_to_diff(text: str) -> str:
        """
        Convert markdown code blocks to unified diff
        Expected format:
        ```python
        # path/to/file.py
        <new content>
        ```
        """
        # Extract code blocks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)

        patches = []
        for block in code_blocks:
            # Try to extract file path from first line
            lines = block.split('\n')
            file_path = None

            # Look for file path in comment or first line
            for line in lines[:5]:  # Check first few lines
                if re.match(r'#\s*([\w/\.\-_]+\.py)', line):
                    file_path = re.match(r'#\s*([\w/\.\-_]+\.py)', line).group(1)
                    break
                elif '/' in line or '\\' in line:
                    # Might be a file path
                    potential_path = line.strip('#').strip()
                    if potential_path.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                        file_path = potential_path
                        break

            if not file_path:
                # Can't generate diff without knowing the file
                continue

            # Remove file path line if present
            content_lines = [l for l in lines if not (file_path in l and l.startswith('#'))]
            new_content = '\n'.join(content_lines)

            # Generate diff (would need original content - placeholder for now)
            patch = PatchAdapter._generate_diff_from_content(file_path, "", new_content)
            patches.append(patch)

        return '\n'.join(patches)

    @staticmethod
    def _convert_json_to_diff(text: str) -> str:
        """Convert JSON file changes to diff"""
        import json
        try:
            data = json.loads(text)

            # Handle different JSON formats
            if 'files' in data:
                # Format: {"files": [{"path": "...", "content": "..."}]}
                patches = []
                for file_info in data['files']:
                    patch = PatchAdapter._generate_diff_from_content(
                        file_info['path'],
                        file_info.get('original', ''),
                        file_info['content']
                    )
                    patches.append(patch)
                return '\n'.join(patches)

            elif 'file_path' in data and 'content' in data:
                # Format: {"file_path": "...", "content": "..."}
                return PatchAdapter._generate_diff_from_content(
                    data['file_path'],
                    data.get('original', ''),
                    data['content']
                )

        except json.JSONDecodeError:
            pass

        return ""

    @staticmethod
    def _convert_plain_code_to_diff(code: str) -> str:
        """Convert plain code to diff (assumes full file replacement)"""
        # Without file path, can't generate valid diff
        # This is a fallback that won't work for SWE-bench
        return ""

    @staticmethod
    def _generate_diff_from_content(file_path: str, original: str, modified: str) -> str:
        """Generate unified diff from original and modified content"""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )

        diff_text = ''.join(diff)

        # Add git diff header
        if diff_text:
            header = f"diff --git a/{file_path} b/{file_path}\n"
            return header + diff_text

        return ""

    @staticmethod
    def validate_patch(patch: str) -> Tuple[bool, Optional[str]]:
        """
        Validate unified diff patch format
        Returns (is_valid, error_message)
        """
        if not patch or not patch.strip():
            return False, "Empty patch"

        if 'diff --git' not in patch:
            return False, "Missing git diff header"

        # Check for basic diff structure
        has_hunks = bool(re.search(r'^@@.*@@', patch, re.MULTILINE))
        if not has_hunks:
            return False, "No diff hunks found"

        # Check for file markers
        has_file_markers = bool(re.search(r'^---.*\n\+\+\+', patch, re.MULTILINE))
        if not has_file_markers:
            return False, "Missing file markers (--- / +++)"

        return True, None

    @staticmethod
    def extract_modified_files(patch: str) -> List[str]:
        """Extract list of files modified in patch"""
        files = []
        matches = re.finditer(r'diff --git a/(.*?) b/', patch)
        for match in matches:
            files.append(match.group(1))
        return files

    @staticmethod
    def count_hunks(patch: str) -> int:
        """Count number of diff hunks in patch"""
        return len(re.findall(r'^@@.*@@', patch, re.MULTILINE))

    @staticmethod
    def get_patch_stats(patch: str) -> Dict:
        """Get statistics about patch"""
        lines = patch.split('\n')

        additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))

        return {
            'files_modified': len(PatchAdapter.extract_modified_files(patch)),
            'hunks': PatchAdapter.count_hunks(patch),
            'lines_added': additions,
            'lines_deleted': deletions,
            'total_changes': additions + deletions
        }


class MAKEROutputParser:
    """Parse MAKER orchestrator output to extract code and metadata"""

    @staticmethod
    def parse_workflow_output(workflow_result: Dict) -> Dict:
        """
        Parse MAKER workflow result
        Extracts:
        - Generated code/patches
        - EE Memory metadata
        - MAKER voting results
        - Reviewer feedback
        """
        parsed = {
            'code': '',
            'patch': '',
            'ee_mode': workflow_result.get('ee_mode', False),
            'narrative_count': workflow_result.get('narrative_count', 0),
            'confidence': workflow_result.get('average_confidence', 0.0),
            'maker_candidates': workflow_result.get('maker_candidates', 0),
            'maker_votes': workflow_result.get('maker_votes', {}),
            'reviewer_approved': False,
            'reviewer_feedback': '',
            'errors': []
        }

        # Extract main output
        output = workflow_result.get('output', '')
        parsed['code'] = output

        # Try to extract patch
        parsed['patch'] = PatchAdapter.extract_patch_from_maker_output(output)

        # Extract reviewer feedback if present
        if 'review' in workflow_result:
            review = workflow_result['review']
            parsed['reviewer_approved'] = 'approved' in review.lower() or 'pass' in review.lower()
            parsed['reviewer_feedback'] = review

        # Check for errors
        if 'error' in workflow_result:
            parsed['errors'].append(workflow_result['error'])

        return parsed

    @staticmethod
    def extract_file_changes(output: str) -> List[Dict[str, str]]:
        """
        Extract file changes from MAKER output
        Returns list of {file_path, original, modified}
        """
        changes = []

        # Try to find file blocks
        # Format: "File: path/to/file.py"
        file_pattern = r'File:\s*([\w/\.\-_]+)\n(.*?)(?=File:|$)'
        matches = re.finditer(file_pattern, output, re.DOTALL | re.MULTILINE)

        for match in matches:
            file_path = match.group(1)
            content = match.group(2).strip()

            changes.append({
                'file_path': file_path,
                'modified': content,
                'original': ''  # Would need to fetch from repo
            })

        return changes


if __name__ == "__main__":
    # Test the adapter
    import sys

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        with open(test_file, 'r') as f:
            content = f.read()

        patch = PatchAdapter.extract_patch_from_maker_output(content)
        is_valid, error = PatchAdapter.validate_patch(patch)

        print(f"Valid patch: {is_valid}")
        if error:
            print(f"Error: {error}")

        if patch:
            stats = PatchAdapter.get_patch_stats(patch)
            print(f"Stats: {stats}")
            print("\nPatch:")
            print(patch)
    else:
        print("Usage: python swe_bench_adapter.py <maker_output_file>")
