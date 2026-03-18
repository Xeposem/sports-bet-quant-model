import { Component, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="flex flex-col items-center justify-center min-h-64 gap-4 p-6"
        >
          <h2 className="text-xl font-semibold text-slate-100">Something went wrong</h2>
          <p className="text-sm text-slate-500">{this.state.error?.message}</p>
          <Button
            variant="outline"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="border-slate-600 text-slate-100 hover:bg-slate-800"
          >
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
