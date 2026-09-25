import { Link } from 'react-router';

/**
 * The page shown for an address the application does not know.
 * @returns The page.
 */
export function NotFoundPage() {
  return (
    <>
      <h1 className="page-title">Page not found</h1>
      <p className="page-subtitle">
        There is nothing at this address. Go back to the <Link to="/overview">overview</Link>.
      </p>
    </>
  );
}
