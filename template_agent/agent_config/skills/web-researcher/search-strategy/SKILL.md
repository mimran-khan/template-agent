---
name: search-strategy
description: Use this skill when researching a sub-question. Provides methodology for effective web searching, source evaluation, and structured finding collection.
---

# Web Research Strategy

## Search Execution
1. **Batch queries**: Use search_web with ALL suggested queries in a single call for efficiency.
2. **Review results**: Scan titles and snippets for relevance before reading full pages.
3. **Select sources**: Pick the 2-4 most relevant and credible sources to read in full.
4. **Deep read**: Use scrape_webpage on selected sources to get full article content.

## When to Use scrape_webpage
- Source appears highly relevant but the snippet is insufficient
- Source contains data, benchmarks, or detailed analysis you need to extract
- Source is from an authoritative domain (official docs, research papers, established publications)

## When NOT to Use scrape_webpage
- The search snippet already provides the needed fact
- The source is a forum post or social media (usually not worth the full read)
- You already have enough evidence for this sub-question

## Source Evaluation Criteria

### Prefer (high credibility)
- Official documentation and specifications
- Peer-reviewed papers and research institutions
- Established tech publications (InfoQ, The Verge, Ars Technica, etc.)
- Company engineering blogs from relevant organizations
- Recent content (prefer last 12 months for fast-moving topics)

### Use With Caution
- Wikipedia (good for background, cite the original sources it references)
- Medium / Dev.to articles (check author credentials)
- Stack Overflow (good for technical specifics, not for analysis)

### Avoid
- AI-generated content farms
- Sources with no author or publication date
- Outdated content on rapidly evolving topics (>2 years old)

## Structured Output
Always include:
- **Key Facts**: Specific, verifiable claims with source attribution
- **Detailed Notes**: Narrative summary connecting the facts
- **Sources Used**: Full URL + one-line relevance note for each
- **Confidence Level**: Based on source quality and corroboration

## Handling Contradictions
When sources disagree:
- Note both positions explicitly
- Indicate which source is more authoritative and why
- Flag the contradiction for the report synthesizer to address
