
import React, { useState } from 'react';
import { TicketForm } from '../tickets/TicketForm';
import { TicketInfo } from '../tickets/TicketInfo';
import { PlannerAgent } from '../agents/PlannerAgent';
import { DeveloperAgent } from '../agents/DeveloperAgent';
import { QAAgent } from '../agents/QAAgent';
import { CommunicatorAgent } from '../agents/CommunicatorAgent';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { toast } from '@/components/ui/sonner';

// Mock data for demonstration
const mockTicket = {
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

const mockPlannerAnalysis = {
  affectedFiles: [
    'src/components/auth/LoginButton.tsx',
    'src/components/auth/LoginModal.tsx',
    'src/hooks/useAuth.ts'
  ],
  rootCause: 'The event handler for the login button uses a non-Safari compatible feature. Specifically, it uses the "once" option in the event listener which is not supported in older Safari versions.',
  suggestedApproach: '1. Modify the LoginButton component to use a standard onClick handler instead of the addEventListener with "once" option.\n2. Ensure the event propagation is manually stopped if needed.\n3. Add a polyfill for older Safari versions that might still be in use.'
};

const mockDiffs = [
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

const mockTestResults = [
  {
    name: 'LoginButton.test.tsx - renders correctly',
    status: 'pass' as const,
    duration: 45
  },
  {
    name: 'LoginButton.test.tsx - opens modal on click',
    status: 'pass' as const,
    duration: 62
  },
  {
    name: 'LoginModal.test.tsx - handles form submission',
    status: 'pass' as const,
    duration: 78
  }
];

const mockUpdates = [
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

export function Dashboard() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTicket, setActiveTicket] = useState<typeof mockTicket | null>(null);
  
  // Agent states
  const [plannerStatus, setPlannerStatus] = useState<'idle' | 'working' | 'success' | 'error' | 'waiting'>('idle');
  const [developerStatus, setDeveloperStatus] = useState<'idle' | 'working' | 'success' | 'error' | 'waiting'>('idle');
  const [qaStatus, setQaStatus] = useState<'idle' | 'working' | 'success' | 'error' | 'waiting'>('idle');
  const [communicatorStatus, setCommunicatorStatus] = useState<'idle' | 'working' | 'success' | 'error' | 'waiting'>('idle');
  
  const [plannerProgress, setPlannerProgress] = useState(0);
  const [developerProgress, setDeveloperProgress] = useState(0);
  const [qaProgress, setQaProgress] = useState(0);
  const [communicatorProgress, setCommunicatorProgress] = useState(0);
  
  // Analysis and results states
  const [plannerAnalysis, setPlannerAnalysis] = useState<typeof mockPlannerAnalysis | undefined>(undefined);
  const [diffs, setDiffs] = useState<typeof mockDiffs | undefined>(undefined);
  const [testResults, setTestResults] = useState<typeof mockTestResults | undefined>(undefined);
  const [updates, setUpdates] = useState<typeof mockUpdates | undefined>(undefined);
  
  // For demo purposes, simulate the process when a ticket is submitted
  const handleTicketSubmit = (ticketId: string) => {
    setIsProcessing(true);
    toast.info(`Starting fix process for ticket ${ticketId}`);
    
    // Reset all states
    setPlannerStatus('idle');
    setDeveloperStatus('idle');
    setQaStatus('idle');
    setCommunicatorStatus('idle');
    
    setPlannerProgress(0);
    setDeveloperProgress(0);
    setQaProgress(0);
    setCommunicatorProgress(0);
    
    setPlannerAnalysis(undefined);
    setDiffs(undefined);
    setTestResults(undefined);
    setUpdates(undefined);
    
    // Simulate fetching the ticket
    setTimeout(() => {
      setActiveTicket(mockTicket);
      
      // Start planner agent
      setPlannerStatus('working');
      
      // Simulate planner progress
      const plannerInterval = setInterval(() => {
        setPlannerProgress(prev => {
          if (prev >= 100) {
            clearInterval(plannerInterval);
            setPlannerStatus('success');
            setPlannerAnalysis(mockPlannerAnalysis);
            
            // Start developer agent after planner is done
            setDeveloperStatus('working');
            
            // Simulate developer progress
            const developerInterval = setInterval(() => {
              setDeveloperProgress(prev => {
                if (prev >= 100) {
                  clearInterval(developerInterval);
                  setDeveloperStatus('success');
                  setDiffs(mockDiffs);
                  
                  // Start QA agent after developer is done
                  setQaStatus('working');
                  
                  // Simulate QA progress
                  const qaInterval = setInterval(() => {
                    setQaProgress(prev => {
                      if (prev >= 100) {
                        clearInterval(qaInterval);
                        setQaStatus('success');
                        setTestResults(mockTestResults);
                        
                        // Start communicator agent after QA is done
                        setCommunicatorStatus('working');
                        
                        // Simulate communicator progress
                        const commInterval = setInterval(() => {
                          setCommunicatorProgress(prev => {
                            if (prev >= 100) {
                              clearInterval(commInterval);
                              setCommunicatorStatus('success');
                              setUpdates(mockUpdates);
                              setIsProcessing(false);
                              
                              toast.success('Fix process completed successfully!', {
                                description: 'PR created and JIRA updated.'
                              });
                              
                              return 100;
                            }
                            return Math.min(prev + 5, 100);
                          });
                        }, 100);
                        
                        return 100;
                      }
                      return Math.min(prev + 5, 100);
                    });
                  }, 100);
                  
                  return 100;
                }
                return Math.min(prev + 2, 100);
              });
            }, 100);
            
            return 100;
          }
          return Math.min(prev + 1, 100);
        });
      }, 100);
      
    }, 1000);
  };
  
  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Fix Bug</CardTitle>
          </CardHeader>
          <CardContent>
            <TicketForm onSubmit={handleTicketSubmit} isProcessing={isProcessing} />
          </CardContent>
        </Card>
        
        <TicketInfo ticket={activeTicket} />
      </div>
      
      <Separator />
      
      <div className="grid gap-6 md:grid-cols-2">
        <PlannerAgent 
          status={plannerStatus} 
          progress={plannerProgress}
          analysis={plannerAnalysis}
        />
        
        <DeveloperAgent 
          status={developerStatus} 
          progress={developerProgress}
          attempt={1}
          maxAttempts={4}
          diffs={diffs}
        />
      </div>
      
      <div className="grid gap-6 md:grid-cols-2">
        <QAAgent 
          status={qaStatus} 
          progress={qaProgress}
          testResults={testResults}
          summary={testResults ? {
            total: testResults.length,
            passed: testResults.filter(t => t.status === 'pass').length,
            failed: testResults.filter(t => t.status === 'fail').length,
            duration: testResults.reduce((acc, curr) => acc + curr.duration, 0)
          } : undefined}
        />
        
        <CommunicatorAgent 
          status={communicatorStatus} 
          progress={communicatorProgress}
          updates={updates}
          prUrl={updates ? "https://github.com/org/repo/pull/45" : undefined}
          jiraUrl={updates ? "https://jira.company.com/browse/DEMO-123" : undefined}
        />
      </div>
    </div>
  );
}
