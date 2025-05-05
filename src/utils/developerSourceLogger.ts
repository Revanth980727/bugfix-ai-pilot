
/**
 * Utility to extract and log GitHub source information
 */

export interface GitHubSource {
  repo_owner?: string;
  repo_name?: string;
  branch?: string;
  default_branch?: string;
  patch_mode?: string;
  commit_sha?: string;
}

/**
 * Extract GitHub source information from environment variables
 */
export function extractGitHubSourceFromEnv(): GitHubSource {
  // In the browser, we can't access environment variables directly
  // This would normally be populated from a backend API
  return {
    repo_owner: process.env.GITHUB_REPO_OWNER || import.meta.env.VITE_GITHUB_REPO_OWNER as string,
    repo_name: process.env.GITHUB_REPO_NAME || import.meta.env.VITE_GITHUB_REPO_NAME as string,
    branch: process.env.GITHUB_BRANCH || import.meta.env.VITE_GITHUB_BRANCH as string,
    default_branch: process.env.GITHUB_DEFAULT_BRANCH || import.meta.env.VITE_GITHUB_DEFAULT_BRANCH as string || 'main',
    patch_mode: process.env.PATCH_MODE || import.meta.env.VITE_PATCH_MODE as string || 'line-by-line',
    commit_sha: process.env.GITHUB_COMMIT_SHA || import.meta.env.VITE_GITHUB_COMMIT_SHA as string
  };
}

/**
 * Log GitHub source information to console
 */
export function logGitHubSource(source: GitHubSource | null): void {
  if (!source) {
    console.log('No GitHub source information available');
    return;
  }
  
  console.log('GitHub Source Information:');
  console.log(`Repository: ${source.repo_owner}/${source.repo_name}`);
  console.log(`Branch: ${source.branch || source.default_branch || 'main'}`);
  console.log(`Patch Mode: ${source.patch_mode || 'line-by-line'}`);
  
  if (source.commit_sha) {
    console.log(`Commit SHA: ${source.commit_sha}`);
  }
}
