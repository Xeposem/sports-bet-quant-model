import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RoiBarChart } from '../components/charts/RoiBarChart';

// Mock @nivo/bar — ResponsiveBar renders nothing meaningful in jsdom
vi.mock('@nivo/bar', () => ({
  ResponsiveBar: () => null,
}));

const positiveData = [
  { id: 'Hard', roi: 12.5 },
  { id: 'Clay', roi: -3.2 },
];

describe('RoiBarChart', () => {
  it('renders container with role="img" and aria-label containing dimension name', () => {
    render(
      <RoiBarChart
        data={positiveData}
        dimension="Surface"
        onBarClick={vi.fn()}
      />
    );
    const container = screen.getByRole('img');
    expect(container).toBeInTheDocument();
    expect(container).toHaveAttribute('aria-label', 'ROI by Surface');
  });

  it('renders with positive data without errors', () => {
    expect(() =>
      render(
        <RoiBarChart
          data={[{ id: 'Grass', roi: 5.1 }]}
          dimension="Surface"
          onBarClick={vi.fn()}
        />
      )
    ).not.toThrow();
  });

  it('renders with negative data without errors', () => {
    expect(() =>
      render(
        <RoiBarChart
          data={[{ id: 'Clay', roi: -8.3 }]}
          dimension="Surface"
          onBarClick={vi.fn()}
        />
      )
    ).not.toThrow();
  });

  it('renders with empty data without errors', () => {
    expect(() =>
      render(
        <RoiBarChart
          data={[]}
          dimension="Year"
          onBarClick={vi.fn()}
        />
      )
    ).not.toThrow();
  });
});
