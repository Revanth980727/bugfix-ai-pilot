
import { GitHubConfig } from '@/types/ticket';
import { isValidGitHubSource } from '@/utils/developerSourceLogger';

/**
 * Get GitHub configuration from environment variables or API
 */
export const getGitHubConfig = async (): Promise<GitHubConfig | null> => {
  try {
    console.log('Fetching GitHub configuration...');
    // In a real app, this would make an API call to the backend
    // For now, we'll just use environment variables or simulated data
    const config: GitHubConfig = {
      repo_owner: process.env.GITHUB_REPO_OWNER || import.meta.env.VITE_GITHUB_REPO_OWNER as string || 'example-org',
      repo_name: process.env.GITHUB_REPO_NAME || import.meta.env.VITE_GITHUB_REPO_NAME as string || 'example-repo',
      default_branch: process.env.GITHUB_DEFAULT_BRANCH || import.meta.env.VITE_GITHUB_DEFAULT_BRANCH as string || 'main',
      branch: process.env.GITHUB_BRANCH || import.meta.env.VITE_GITHUB_BRANCH as string || 'feature/bugfix',
      patch_mode: (process.env.PATCH_MODE || import.meta.env.VITE_PATCH_MODE as string || 'line-by-line') as 'intelligent' | 'line-by-line' | 'direct'
    };
    
    // Log the config for debugging (without sensitive data)
    console.log(`GitHub config loaded: ${config.repo_owner}/${config.repo_name}`);
    console.log(`Using branch: ${config.branch} (default: ${config.default_branch})`);
    console.log(`Using patch mode: ${config.patch_mode}`);
    
    // Log raw environment variables (redacted) for debugging
    console.log('Environment variables present:', {
      GITHUB_REPO_OWNER: Boolean(process.env.GITHUB_REPO_OWNER),
      VITE_GITHUB_REPO_OWNER: Boolean(import.meta.env.VITE_GITHUB_REPO_OWNER),
      GITHUB_REPO_NAME: Boolean(process.env.GITHUB_REPO_NAME),
      VITE_GITHUB_REPO_NAME: Boolean(import.meta.env.VITE_GITHUB_REPO_NAME)
    });
    
    // Validate the configuration
    const valid = isValidGitHubSource(config);
    if (!valid) {
      console.warn('GitHub configuration is incomplete or invalid');
    }
    
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
  console.log(`Generating diff for file: ${filename}`);
  
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
  
  console.log(`Generated ${diff.split('\n').length} lines of diff`);
  return diff;
};

/**
 * Check if a file exists in the repository
 * Note: In this frontend-only implementation, this is a mock function
 */
export const checkFileExists = async (filePath: string): Promise<boolean> => {
  console.log(`Checking if file exists: ${filePath}`);
  try {
    // In a real implementation, this would call the backend
    // For testing, simulate file existence
    const result = true;
    console.log(`File ${filePath} exists: ${result}`);
    return result;
  } catch (error) {
    console.error(`Error checking if file exists [${filePath}]:`, error);
    return false;
  }
};

/**
 * Get file content from repository
 * Note: In this frontend-only implementation, this is a mock function
 */
export const getFileContent = async (filePath: string): Promise<string | null> => {
  console.log(`Attempting to get content for file: ${filePath}`);
  
  try {
    // In a real implementation, this would call the backend API
    // For testing, return mock content based on file type
    let mockContent = `// Mock content for ${filePath}\n// This would be the actual file content in a real implementation\n\n`;
    
    if (filePath.endsWith('.py')) {
      mockContent += `import os\nimport sys\n\ndef main():\n    print("This is mock Python content")\n\nif __name__ == "__main__":\n    main()\n`;
    } else if (filePath.endsWith('.js') || filePath.endsWith('.ts')) {
      mockContent += `function exampleCode() {\n  console.log("This is mock JavaScript content");\n}\n\nexport default exampleCode;\n`;
    } else {
      mockContent += `function exampleCode() {\n  console.log("This is mock content");\n}\n`;
    }
    
    console.log(`Successfully generated mock content for ${filePath} (${mockContent.length} bytes)`);
    return mockContent;
  } catch (error) {
    console.error(`Failed to get content for ${filePath}:`, error);
    return null;
  }
};
