import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PropsTab } from '../tabs/PropsTab';

// Mock all hooks
vi.mock('../hooks/useProps', () => ({
  useProps: vi.fn(),
  useSubmitPropLine: vi.fn(),
  usePropAccuracy: vi.fn(),
  useScanPropScreenshot: vi.fn(),
}));

// Mock PropScanPreview to avoid QueryClient dependency
vi.mock('../components/shared/PropScanPreview', () => ({
  PropScanPreview: () => <div data-testid="prop-scan-preview">PropScanPreview</div>,
}));

// Mock charts to avoid jsdom/WebGL rendering issues
vi.mock('../components/charts/PmfChart', () => ({
  PmfChart: () => <div role="img" aria-label="PMF chart" />,
}));
vi.mock('../components/charts/CalibrationChart', () => ({
  CalibrationChart: () => <div data-testid="calibration-chart">CalibrationChart</div>,
}));
vi.mock('@nivo/bar', () => ({
  ResponsiveBar: () => <div data-testid="responsive-bar">ResponsiveBar</div>,
}));

import { useProps, useSubmitPropLine, usePropAccuracy, useScanPropScreenshot } from '../hooks/useProps';

const defaultPropsData = {
  data: { status: 'ok', data: [] },
  isLoading: false,
  isError: false,
};

const defaultAccuracyData = {
  data: {
    status: 'ok',
    overall_hit_rate: null,
    hit_rate_by_stat: {},
    total_tracked: 0,
    rolling_30d: [],
    calibration_bins: [],
  },
  isLoading: false,
  isError: false,
};

const defaultMutateData = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
};

const defaultScanMutateData = {
  mutateAsync: vi.fn(),
  isPending: false,
  isError: false,
};

function setupDefaultMocks() {
  vi.mocked(useProps).mockReturnValue(defaultPropsData as any);
  vi.mocked(useSubmitPropLine).mockReturnValue(defaultMutateData as any);
  vi.mocked(usePropAccuracy).mockReturnValue(defaultAccuracyData as any);
  vi.mocked(useScanPropScreenshot).mockReturnValue(defaultScanMutateData as any);
}

describe('PropsTab', () => {
  it('renders Props tab heading', () => {
    setupDefaultMocks();
    render(<PropsTab />);
    expect(screen.getByText('Enter Prop Line')).toBeInTheDocument();
  });

  it('renders KPI cards', () => {
    setupDefaultMocks();
    render(<PropsTab />);
    expect(screen.getByText('Hit Rate')).toBeInTheDocument();
    expect(screen.getByText('Props Tracked')).toBeInTheDocument();
  });

  it('renders empty state when no props', () => {
    setupDefaultMocks();
    render(<PropsTab />);
    expect(screen.getByText('No props tracked yet')).toBeInTheDocument();
  });

  it('shows loading skeletons when accuracy is loading', () => {
    vi.mocked(useProps).mockReturnValue(defaultPropsData as any);
    vi.mocked(useSubmitPropLine).mockReturnValue(defaultMutateData as any);
    vi.mocked(usePropAccuracy).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any);

    render(<PropsTab />);
    const skeletons = screen.getAllByRole('generic').filter(
      (el) => el.getAttribute('aria-busy') === 'true'
    );
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders Check Prop submit button', () => {
    setupDefaultMocks();
    render(<PropsTab />);
    expect(screen.getByText('Check Prop')).toBeInTheDocument();
  });

  it('renders Predicted Distribution section', () => {
    setupDefaultMocks();
    render(<PropsTab />);
    expect(screen.getByText('Predicted Distribution')).toBeInTheDocument();
  });
});
