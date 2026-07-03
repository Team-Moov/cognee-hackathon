import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

class LiteratureAgent:
    def __init__(self):
        # Local JSON state no longer required for token extraction
        pass

    def fetch_grounding_literature(self):
        print("\n[*] Literature Agent waiting for target parameters...")
        
        while True:
            manual_tokens = input("[?] Enter 2-3 search terms/keywords (separated by spaces): ").strip()
            if manual_tokens:
                break
            print("[!] Keywords cannot be blank. Please try again.")
            
        # Formulate query string with clean spacing splits
        search_query = " AND ".join(manual_tokens.split())
        print(f"    - Executing live open-access lookup via string criteria: '{search_query}'")
        
        encoded_query = urllib.parse.quote(f"all:{search_query}")
        url = f"http://export.arxiv.org/api/query?search_query={encoded_query}&max_results=3"
        
        matched_papers = []
        try:
            response = urllib.request.urlopen(url, timeout=10)
            root = ET.fromstring(response.read())
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
                authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
                
                matched_papers.append({
                    "title": title,
                    "authors": authors,
                    "live_abstract_snippet": summary[:250] + "...",
                    "relevance_rationale": f"Matched via explicit user override parameters: '{search_query}'"
                })
        except Exception as api_err:
            print(f"    [!] Open-access web query warning: {api_err}. Continuing with empty array.")

        return {
            "subagent": "LiteratureAgent",
            "analyzed_hypothesis_context": f"Manual query override tokens: {manual_tokens}",
            "extracted_search_criteria": search_query,
            "academic_grounding_nodes": matched_papers
        }
