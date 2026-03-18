import { useState } from 'react';
import { useModels } from '../hooks/useModels';
import { useCalibration } from '../hooks/useCalibration';
import { ModelComparisonTable } from '../components/shared/ModelComparisonTable';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import { EmptyState } from '../components/shared/EmptyState';
import { SkeletonCard } from '../components/shared/SkeletonCard';

export function ModelsTab() {
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const models = useModels();
  const calibration = useCalibration(selectedModel ?? undefined);

  if (models.isLoading) {
    return (
      <div className="p-6">
        <SkeletonCard variant="table" />
      </div>
    );
  }

  if (models.isError) {
    return (
      <div className="p-6" role="alert">
        <p className="text-red-500">
          Failed to load data. Check that the API server is running on port 8000.
        </p>
      </div>
    );
  }

  const modelList = models.data?.data ?? [];

  if (modelList.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          heading="No models found"
          body="Train at least one model before viewing comparisons."
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <ModelComparisonTable
        models={modelList}
        selectedModel={selectedModel}
        onSelectModel={setSelectedModel}
      />

      <div>
        {selectedModel === null ? (
          <p className="text-sm text-slate-500 text-center py-8">
            Click a model row above to view its calibration diagram
          </p>
        ) : calibration.isLoading ? (
          <SkeletonCard variant="chart" height={240} />
        ) : calibration.data ? (
          <div
            style={{ opacity: 1, transition: 'opacity 150ms ease-out' }}
          >
            <CalibrationChart
              bins={calibration.data.bins}
              modelVersion={calibration.data.model_version}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
