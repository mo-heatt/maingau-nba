import {describe, expect, it} from 'vitest';
import {categoryLink} from '../components/productPresentation';

describe('categoryLink', () => {
  it('maps every product category to its verified MAINGAU page', () => {
    expect(categoryLink('electricity').url).toBe('https://www.maingau-energie.de/strom');
    expect(categoryLink('gas').url).toBe('https://www.maingau-energie.de/gas');
    expect(categoryLink('mobile').url).toBe('https://www.maingau-energie.de/mobilfunk');
    expect(categoryLink('internet').url).toBe('https://www.maingau-energie.de/internet');
    expect(categoryLink('charging').url).toBe('https://www.maingau-energie.de/e-mobilitaet/autostrom');
    expect(categoryLink('devices').url).toBe('https://www.maingau-energie.de/smart-living');
    expect(categoryLink('shop').url).toBe('https://www.maingau-energie.de/onlineshop');
  });

  it('falls back to the MAINGAU homepage for unknown categories', () => {
    const link = categoryLink('other');
    expect(link.url).toBe('https://www.maingau-energie.de/');
    expect(link.label).toBe('MAINGAU website');
  });

  it('always links to the maingau-energie.de domain', () => {
    for (const category of ['electricity', 'gas', 'mobile', 'internet', 'charging', 'devices', 'shop', 'unknown']) {
      expect(categoryLink(category).url.startsWith('https://www.maingau-energie.de')).toBe(true);
    }
  });
});
