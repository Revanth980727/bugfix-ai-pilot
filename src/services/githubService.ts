
import { GitHubConfig } from '@/types/ticket';

/**
 * Get GitHub configuration from environment variables or API
 */
export const getGitHubConfig = async (): Promise<GitHubConfig | null> => {
  try {
    // In a real app, this would make an API call to the backend
    // For now, we'll just use environment variables or simulated data
    const config: GitHubConfig = {
      repo_owner: process.env.GITHUB_REPO_OWNER || import.meta.env.VITE_GITHUB_REPO_OWNER as string || 'example-org',
      repo_name: process.env.GITHUB_REPO_NAME || import.meta.env.VITE_GITHUB_REPO_NAME as string || 'example-repo',
      default_branch: process.env.GITHUB_DEFAULT_BRANCH || import.meta.env.VITE_GITHUB_DEFAULT_BRANCH as string || 'main',
      branch: process.env.GITHUB_BRANCH || import.meta.env.VITE_GITHUB_BRANCH as string || 'feature/bugfix',
      patch_mode: (process.env.PATCH_MODE || import.meta.env.VITE_PATCH_MODE as string || 'line-by-line') as 'intelligent' | 'line-by-line' | 'direct'
    };
    
    return config;
  } catch (error) {
    console.error('Failed to get GitHub configuration:', error);
    return null;
  }
};

/**
 * Generate a patch/diff between original and modified file content
 */
export const generateDiff = (originalContent: string, modifiedContent: string, filename: string): string => {
  // This is a simplified diff generation - in a real app, you'd use a proper diff library
  const originalLines = originalContent.split('\n');
  const modifiedLines = modifiedContent.split('\n');
  
  // Mock diff generation - in reality this would use a proper diff algorithm
  let diff = `--- a/${filename}\n+++ b/${filename}\n`;
  
  // Find some line numbers for the mock diff
  const lineNum = Math.min(originalLines.length, 5);
  diff += `@@ -${lineNum},3 +${lineNum},3 @@\n`;
  
  // Add some context lines
  for (let i = Math.max(0, lineNum - 2); i < lineNum; i++) {
    diff += ` ${originalLines[i] || ''}\n`;
  }
  
  // Add a removed line
  diff += `-${originalLines[lineNum] || ''}\n`;
  
  // Add an added line
  diff += `+${modifiedLines[lineNum] || originalLines[lineNum] + ' // modified'}\n`;
  
  // Add more context
  for (let i = lineNum + 1; i < lineNum + 3 && i < originalLines.length; i++) {
    diff += ` ${originalLines[i] || ''}\n`;
  }
  
  return diff;
};
