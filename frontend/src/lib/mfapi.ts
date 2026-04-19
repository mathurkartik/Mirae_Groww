/**
 * mfapi.ts — Fetch historical NAV data from MFAPI.in and calculate CAGR
 * 
 * MFAPI endpoint: https://api.mfapi.in/mf/{scheme_code}
 * Returns: {data: [{date: "DD-MM-YYYY", nav: "123.45"}, ...]}
 */

export interface NAVDataPoint {
  date: string;  // "DD-MM-YYYY"
  nav: string;   // "123.45"
}

export interface MFAPIResponse {
  meta: {
    scheme_code: string;
    scheme_name: string;
  };
  data: NAVDataPoint[];
  status: string;
}

/**
 * Calculate CAGR between two NAV values over a given period.
 * Formula: CAGR = ((End Value / Start Value)^(1/years) - 1) * 100
 */
function calculateCAGR(startNav: number, endNav: number, years: number): number {
  if (startNav <= 0 || years <= 0) return 0;
  const cagr = (Math.pow(endNav / startNav, 1 / years) - 1) * 100;
  return Math.round(cagr * 100) / 100; // Round to 2 decimals
}

/**
 * Parse DD-MM-YYYY string to Date object
 */
function parseDate(dateStr: string): Date {
  const [day, month, year] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/**
 * Get NAV data point closest to target date (within ±7 days tolerance)
 */
function getNavNearDate(data: NAVDataPoint[], targetDate: Date): NAVDataPoint | null {
  const tolerance = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds
  
  let closest: NAVDataPoint | null = null;
  let minDiff = Infinity;
  
  for (const point of data) {
    const pointDate = parseDate(point.date);
    const diff = Math.abs(pointDate.getTime() - targetDate.getTime());
    
    if (diff < minDiff && diff <= tolerance) {
      minDiff = diff;
      closest = point;
    }
  }
  
  return closest;
}

/**
 * Fetch fund's historical returns (1Y, 3Y, 5Y CAGR) from MFAPI
 */
export async function fetchHistoricalReturns(mfapiCode: number): Promise<{
  returns_1y: number | null;
  returns_3y: number | null;
  returns_5y: number | null;
  latest_nav: number | null;
  latest_date: string | null;
}> {
  try {
    const response = await fetch(`https://api.mfapi.in/mf/${mfapiCode}`);
    
    if (!response.ok) {
      console.error(`MFAPI fetch failed: ${response.status}`);
      return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
    }
    
    const json: MFAPIResponse = await response.json();
    
    if (json.status !== "SUCCESS" || !json.data || json.data.length === 0) {
      console.error("MFAPI returned no data");
      return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
    }
    
    // Data is sorted newest → oldest, so [0] is latest NAV
    const latest = json.data[0];
    const latestNav = parseFloat(latest.nav);
    const latestDate = parseDate(latest.date);
    
    // Calculate target dates
    const oneYearAgo = new Date(latestDate);
    oneYearAgo.setFullYear(latestDate.getFullYear() - 1);
    
    const threeYearsAgo = new Date(latestDate);
    threeYearsAgo.setFullYear(latestDate.getFullYear() - 3);
    
    const fiveYearsAgo = new Date(latestDate);
    fiveYearsAgo.setFullYear(latestDate.getFullYear() - 5);
    
    // Find NAVs at target dates
    const nav1y = getNavNearDate(json.data, oneYearAgo);
    const nav3y = getNavNearDate(json.data, threeYearsAgo);
    const nav5y = getNavNearDate(json.data, fiveYearsAgo);
    
    // Calculate CAGR
    const returns_1y = nav1y ? calculateCAGR(parseFloat(nav1y.nav), latestNav, 1) : null;
    const returns_3y = nav3y ? calculateCAGR(parseFloat(nav3y.nav), latestNav, 3) : null;
    const returns_5y = nav5y ? calculateCAGR(parseFloat(nav5y.nav), latestNav, 5) : null;
    
    return {
      returns_1y,
      returns_3y,
      returns_5y,
      latest_nav: latestNav,
      latest_date: latest.date,
    };
    
  } catch (error) {
    console.error("MFAPI fetch error:", error);
    return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
  }
}
