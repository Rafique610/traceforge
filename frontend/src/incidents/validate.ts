export function validateGitHubUrl(url: string): string | null {
  const u = url.trim()
  if (!u) return 'Enter a GitHub issue URL.'
  if (u.length > 300) return 'URL is longer than 300 characters.'
  if (!/^https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/(issues|pull)\/\d+\/?$/.test(u))
    return 'Use a URL like https://github.com/owner/repo/issues/123.'
  return null
}
