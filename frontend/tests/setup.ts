import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Testing Library unmounts after each test on its own only when Vitest globals are on; they are off.
afterEach(cleanup);
