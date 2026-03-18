import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ModelsTab } from '../tabs/ModelsTab';

vi.mock('../hooks/useModels', () => ({
  useModels: vi.fn(() => ({
    isLoading: false,
    isError: false,
    data: {
      data: [
        {
          model_version: 'logistic_v1',
          brier_score: 0.21,
          log_loss: 0.65,
          calibration_quality: 'good',
          kelly_roi: 3.5,
          flat_roi: 1.2,
          total_bets: 500,
        },
      ],
    },
  })),
}));

vi.mock('../hooks/useCalibration', () => ({
  useCalibration: vi.fn(() => ({
    isLoading: false,
    isError: false,
    data: null,
  })),
}));

vi.mock('../components/charts/CalibrationChart', () => ({
  CalibrationChart: () => <div data-testid="calibration-chart">CalibrationChart</div>,
}));

describe('ModelsTab', () => {
  it('renders model table with logistic_v1', () => {
    render(<ModelsTab />);
    expect(screen.getByText('logistic_v1')).toBeInTheDocument();
  });

  it('renders column headers', () => {
    render(<ModelsTab />);
    expect(screen.getByText(/brier score/i)).toBeInTheDocument();
    expect(screen.getByText(/log loss/i)).toBeInTheDocument();
    // Use getAllByText for "Calibration" since it appears in the column header and prompt text
    const calibrationElements = screen.getAllByText(/^calibration$/i);
    expect(calibrationElements.length).toBeGreaterThan(0);
    expect(screen.getByText(/kelly roi/i)).toBeInTheDocument();
  });

  it('shows empty state when models data is empty', async () => {
    const { useModels } = await import('../hooks/useModels');
    vi.mocked(useModels).mockReturnValueOnce({
      isLoading: false,
      isError: false,
      data: { data: [] },
    } as unknown as ReturnType<typeof useModels>);
    render(<ModelsTab />);
    expect(screen.getByText('No models found')).toBeInTheDocument();
  });

  it('shows click prompt when no model selected', () => {
    render(<ModelsTab />);
    expect(
      screen.getByText(/click a model row above to view its calibration diagram/i)
    ).toBeInTheDocument();
  });
});
