import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import type { CalibrationBin } from '../api/types';

// Mock @nivo/scatterplot — jsdom can't render SVG charts
vi.mock('@nivo/scatterplot', () => ({
  ResponsiveScatterPlot: () => null,
}));

const sampleBins: CalibrationBin[] = [
  { midpoint: 0.1, empirical_freq: 0.08, n_samples: 50 },
  { midpoint: 0.3, empirical_freq: 0.28, n_samples: 80 },
  { midpoint: 0.5, empirical_freq: 0.52, n_samples: 100 },
  { midpoint: 0.7, empirical_freq: 0.69, n_samples: 90 },
  { midpoint: 0.9, empirical_freq: 0.88, n_samples: 40 },
];

describe('CalibrationChart', () => {
  it('renders container div with role="img" and aria-label', () => {
    render(<CalibrationChart bins={sampleBins} />);
    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      'Calibration reliability diagram'
    );
  });

  it('shows empty state when bins are empty', () => {
    render(<CalibrationChart bins={[]} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Calibration data unavailable/i)).toBeInTheDocument();
  });
});
