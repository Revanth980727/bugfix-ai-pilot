
import { toast } from "sonner";

export interface GitHubSource {
  repo_owner: string;
  repo_name: string;
  branch: string;
  file_path?: string;
}

export const logGitHubSource = (source: GitHubSource) => {
  console.log("GitHub Source Information:", source);
  toast.info(
    `GitHub Source: ${source.repo_owner}/${source.repo_name} @ ${source.branch}${
      source.file_path ? ` - ${source.file_path}` : ""
    }`,
    {
      duration: 5000,
    }
  );
};

export const extractGitHubSourceFromEnv = (): GitHubSource => {
  return {
    repo_owner: process.env.GITHUB_REPO_OWNER || 'unknown',
    repo_name: process.env.GITHUB_REPO_NAME || 'unknown',
    branch: process.env.GITHUB_DEFAULT_BRANCH || 'main',
  };
};
