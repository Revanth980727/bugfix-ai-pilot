
import { Ticket, PlannerAnalysis, CodeDiff, TestResult, Update } from '../types/ticket';

export const mockTicket: Ticket = {
  id: 'DEMO-123',
  title: 'Login button not working on Safari browser',
  description: 'Users have reported that the login button on the homepage does not respond to clicks when using Safari on macOS. This issue does not occur in Chrome or Firefox. Steps to reproduce:\n1. Open the homepage in Safari\n2. Click on the login button\n3. Nothing happens\n\nExpected: Login modal should appear.',
  status: 'Open',
  priority: 'High',
  reporter: 'John Doe',
  assignee: null,
  created: '2025-04-23T10:30:00Z',
  updated: '2025-04-24T08:15:00Z',
};

export const mockPlannerAnalysis: PlannerAnalysis = {
  affectedFiles: [
    'src/components/auth/LoginButton.tsx',
    'src/components/auth/LoginModal.tsx',
    'src/hooks/useAuth.ts'
  ],
  rootCause: 'The event handler for the login button uses a non-Safari compatible feature. Specifically, it uses the "once" option in the event listener which is not supported in older Safari versions.',
  suggestedApproach: '1. Modify the LoginButton component to use a standard onClick handler instead of the addEventListener with "once" option.\n2. Ensure the event propagation is manually stopped if needed.\n3. Add a polyfill for older Safari versions that might still be in use.'
};

export const mockDiffs: CodeDiff[] = [
  {
    filename: 'src/components/auth/LoginButton.tsx',
    diff: `@@ -15,11 +15,9 @@
 
 const LoginButton = () => {
   const { openLoginModal } = useAuth();
-  const buttonRef = useRef<HTMLButtonElement>(null);
   
-  useEffect(() => {
-    buttonRef.current?.addEventListener('click', openLoginModal, { once: true });
-  }, []);
+  const handleClick = () => {
+    openLoginModal();
+  };
   
   return (
     <button
@@ -27,7 +25,7 @@
       className="btn btn-primary"
-      ref={buttonRef}
+      onClick={handleClick}
     >
       Login
     </button>`,
    linesAdded: 4,
    linesRemoved: 7
  }
];

export const mockTestResults: TestResult[] = [
  {
    name: 'LoginButton.test.tsx - renders correctly',
    status: 'pass',
    duration: 45
  },
  {
    name: 'LoginButton.test.tsx - opens modal on click',
    status: 'pass',
    duration: 62
  },
  {
    name: 'LoginModal.test.tsx - handles form submission',
    status: 'pass',
    duration: 78
  }
];

export const mockUpdates: Update[] = [
  {
    timestamp: '2025-04-25T14:30:15Z',
    message: 'Updated JIRA ticket DEMO-123 status to "In Progress"',
    type: 'jira'
  },
  {
    timestamp: '2025-04-25T14:32:45Z',
    message: 'Created branch fix/DEMO-123-safari-login-button',
    type: 'github'
  },
  {
    timestamp: '2025-04-25T14:35:12Z',
    message: 'Committed changes: Fix Safari compatibility issue in LoginButton',
    type: 'github'
  },
  {
    timestamp: '2025-04-25T14:36:30Z',
    message: 'Created pull request #45: Fix Safari login button issue (DEMO-123)',
    type: 'github'
  },
  {
    timestamp: '2025-04-25T14:37:05Z',
    message: 'Added comment to DEMO-123 with PR link and fix description',
    type: 'jira'
  },
  {
    timestamp: '2025-04-25T14:37:30Z',
    message: 'Updated JIRA ticket DEMO-123 status to "Fixed"',
    type: 'jira'
  }
];

