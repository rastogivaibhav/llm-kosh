export function searchPrompts(query, prompts) {
  if (!query || query.trim() === '') {
    return prompts;
  }
  
  const lowerQuery = query.toLowerCase().trim();
  
  return prompts.filter(prompt => {
    const titleMatch = prompt.title.toLowerCase().includes(lowerQuery);
    const descMatch = prompt.description.toLowerCase().includes(lowerQuery);
    const tagMatch = prompt.tags.some(tag => tag.toLowerCase().includes(lowerQuery));
    
    return titleMatch || descMatch || tagMatch;
  });
}
