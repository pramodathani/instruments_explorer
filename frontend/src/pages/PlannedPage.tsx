import { TiltCard } from '../components/TiltCard';

/** Props for PlannedPage. */
interface PlannedPageProps {
  title: string;
  description: string;
  phase: number;
  items: string[];
}

/**
 * A page that is planned but not built yet, saying what it will hold and in which phase it arrives.
 * @param props The page's title, a description, its build phase and what it will contain.
 * @returns The page.
 */
export function PlannedPage(props: PlannedPageProps) {
  const { title, description, phase, items } = props;
  return (
    <div className="planned-page">
      <h1 className="page-title">{title}</h1>
      <p className="page-subtitle">{description}</p>
      <TiltCard>
        <div className="tilt-lift">
          <div className="card-title">
            <h2>What this page will hold</h2>
            <span className="chip">Phase {phase}</span>
          </div>
          <ul className="planned-list">
            {items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </TiltCard>
    </div>
  );
}
