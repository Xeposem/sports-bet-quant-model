import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../App';

describe('App', () => {
  it('renders the Tennis Quant header', () => {
    render(<App />);
    expect(screen.getByText('Tennis Quant')).toBeInTheDocument();
  });

  it('renders all 4 tab triggers', () => {
    render(<App />);
    expect(screen.getByRole('tab', { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /backtest/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /signals/i })).toBeInTheDocument();
  });

  it('shows Overview tab content by default', () => {
    render(<App />);
    // The Overview heading in the tab content panel
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
  });
});
