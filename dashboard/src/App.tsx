import { useState } from 'react';
import { Plus } from 'lucide-react';
import { QueryProvider } from './providers/QueryProvider';
import { Header } from './components/layout/Header';
import { TabNav } from './components/layout/TabNav';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from './components/shared/ErrorBoundary';
import { ManualEntryModal } from './components/modals/ManualEntryModal';

function App() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <QueryProvider>
      <div className="min-h-screen bg-background text-foreground">
        <Header />
        <ErrorBoundary>
          <TabNav />
        </ErrorBoundary>
        <Toaster />
        {/* Floating Action Button — accessible from any tab */}
        <button
          onClick={() => setModalOpen(true)}
          className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-full bg-green-500 hover:bg-green-600 text-white shadow-lg flex items-center justify-center"
          aria-label="Enter Data"
        >
          <Plus className="h-6 w-6" />
        </button>
        <ManualEntryModal open={modalOpen} onOpenChange={setModalOpen} />
      </div>
    </QueryProvider>
  );
}

export default App;
