import { Pipe, PipeTransform } from '@angular/core';

/**
 * Formats a raw number of rupees as "X.X LPA" (lakhs per annum) - matching
 * how salary targets are expressed in the candidate taxonomy (e.g. the
 * 25-30 LPA target from the project's original scope).
 */
@Pipe({ name: 'lpaCurrency', standalone: true })
export class LpaCurrencyPipe implements PipeTransform {
  transform(annualRupees: number | null | undefined): string {
    if (annualRupees == null) return '—';
    const lakhs = annualRupees / 100_000;
    return `${lakhs.toFixed(1)} LPA`;
  }
}
