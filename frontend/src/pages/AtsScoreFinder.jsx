import { useMemo, useState } from "react";
import { BriefcaseBusiness, CheckCircle2, FileText, Search, Sparkles } from "lucide-react";
import "./AtsScoreFinder.css";

const STOP_WORDS = new Set([
  "about", "above", "after", "again", "against", "also", "among", "and", "any", "are", "because", "been", "before", "being", "below", "between", "both", "but", "can", "could", "did", "does", "doing", "during", "each", "few", "for", "from", "further", "had", "has", "have", "having", "here", "hers", "him", "his", "how", "into", "its", "itself", "just", "more", "most", "not", "now", "only", "other", "our", "out", "over", "own", "same", "she", "should", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "through", "too", "under", "until", "very", "was", "were", "what", "when", "where", "which", "while", "who", "will", "with", "would", "you", "your", "work", "working", "experience", "years", "year", "job", "role", "required", "requirements", "preferred", "candidate", "ability", "strong", "including", "using", "used", "use", "well", "must", "good", "excellent", "responsibilities", "responsibility", "skills", "skill", "knowledge", "team", "teams", "etc",
]);

const extractKeywords = (text) =>
  [...new Set((text.toLowerCase().match(/[a-z][a-z+#.-]*/g) || [])
    .map((word) => word.replace(/^[.-]+|[.-]+$/g, ""))
    .filter((word) => word.length > 2 && !STOP_WORDS.has(word)))];

function calculateMatch(resume, jobDescription) {
  const resumeWords = new Set(extractKeywords(resume));
  const jobKeywords = extractKeywords(jobDescription);
  const matched = jobKeywords.filter((keyword) => resumeWords.has(keyword));
  const missing = jobKeywords.filter((keyword) => !resumeWords.has(keyword));

  return {
    score: jobKeywords.length ? Math.round((matched.length / jobKeywords.length) * 100) : 0,
    matched: [...new Set(matched)],
    missing: [...new Set(missing)],
    total: jobKeywords.length,
  };
}

const getScoreLabel = (score) => {
  if (score >= 75) return "Strong match";
  if (score >= 50) return "Good starting point";
  return "Room to improve";
};

export default function AtsScoreFinder() {
  const [resume, setResume] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const scoreColor = useMemo(() => {
    if (!result) return "#2563eb";
    if (result.score >= 75) return "#16805d";
    if (result.score >= 50) return "#d18a16";
    return "#d45151";
  }, [result]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!resume.trim() || !jobDescription.trim()) {
      setError("Add both your resume text and the job description to get a score.");
      setResult(null);
      return;
    }

    const analysis = calculateMatch(resume, jobDescription);
    if (!analysis.total) {
      setError("We couldn't find keywords in the job description. Try adding more detail.");
      setResult(null);
      return;
    }

    setError("");
    setResult(analysis);
  };

  return (
    <main className="ats-page">
      <section className="ats-hero">
        <div className="ats-hero-inner">
          <span className="ats-eyebrow"><Sparkles size={15} /> RESUME MATCH CHECKER</span>
          <h1>Make your resume <span>match the job.</span></h1>
          <p>Compare your resume with a job description and see which important keywords are present or missing.</p>
        </div>
      </section>

      <section className="ats-content container">
        <form className="ats-form" onSubmit={handleSubmit}>
          <div className="ats-input-card">
            <label htmlFor="resume-text"><FileText size={18} /> Your resume</label>
            <p>Paste the text from your resume.</p>
            <textarea id="resume-text" value={resume} onChange={(event) => setResume(event.target.value)} placeholder="Paste your resume text here…" rows={12} />
            <span className="ats-char-count">{resume.length} characters</span>
          </div>
          <div className="ats-input-card">
            <label htmlFor="job-text"><BriefcaseBusiness size={18} /> Job description</label>
            <p>Paste the job listing you want to apply for.</p>
            <textarea id="job-text" value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} placeholder="Paste the job description here…" rows={12} />
            <span className="ats-char-count">{jobDescription.length} characters</span>
          </div>
          {error && <p className="ats-error" role="alert">{error}</p>}
          <button className="ats-submit" type="submit"><Search size={18} /> Calculate my match</button>
          <p className="ats-privacy">Your text is analyzed in this browser and is not uploaded or saved.</p>
        </form>

        {result && (
          <section className="ats-results" aria-live="polite">
            <div className="ats-score-card">
              <div className="ats-score-ring" style={{ "--score-color": scoreColor, "--score": `${result.score}%` }}>
                <div><strong>{result.score}%</strong><span>match score</span></div>
              </div>
              <div className="ats-score-copy">
                <span className="ats-eyebrow">YOUR RESULTS</span>
                <h2>{getScoreLabel(result.score)}</h2>
                <p>{result.matched.length} of {result.total} job-description keywords were found in your resume.</p>
              </div>
            </div>
            <div className="ats-keyword-grid">
              <KeywordCard title="Keywords found" words={result.matched} variant="matched" />
              <KeywordCard title="Keywords to consider" words={result.missing} variant="missing" />
            </div>
            <p className="ats-disclaimer"><CheckCircle2 size={16} /> This is a simple keyword comparison, not a guarantee of how an employer’s ATS will rank your application. Only add skills and experience that accurately reflect your background.</p>
          </section>
        )}
      </section>
    </main>
  );
}

function KeywordCard({ title, words, variant }) {
  return (
    <div className={`ats-keyword-card ${variant}`}>
      <h3>{title} <span>{words.length}</span></h3>
      {words.length ? <div className="ats-tags">{words.map((word) => <span className="ats-tag" key={word}>{word}</span>)}</div> : <p>{variant === "matched" ? "No matching keywords yet." : "Great — no missing keywords found."}</p>}
    </div>
  );
}
