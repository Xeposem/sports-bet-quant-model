import { QueryProvider } from './providers/QueryProvider';
import { Header } from './components/layout/Header';
import { TabNav } from './components/layout/TabNav';
import { Toaster } from '@/components/ui/sonner';

function App() {
  return (
    <QueryProvider>
      <div className="min-h-screen bg-background text-foreground">
        <Header />
        <TabNav />
        <Toaster />
      </div>
    </QueryProvider>
  );
}

export default App;
