import { Button } from '@/components/ui/button';

interface EmptyStateProps {
  heading: string;
  body: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ heading, body, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12" role="status">
      <p className="text-lg font-semibold text-slate-100">{heading}</p>
      <p className="text-sm text-slate-500 mt-2">{body}</p>
      {action && (
        <Button variant="outline" onClick={action.onClick} className="mt-4">
          {action.label}
        </Button>
      )}
    </div>
  );
}
