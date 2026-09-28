"""Editorial behavior switches; independent of vendors and storage."""


def experimental(project):
    job = project.get("job") or {}
    if "editorial_policy" in job:
        return job["editorial_policy"] in {2, 3}
    # A received legacy draft belongs to its old contract, even if the author
    # has selected a different edition for future calls in the meantime.
    if job.get("editorial_fingerprint") or job.get("response_contract_version"):
        return False
    return (project.get("writing_edition") or {}).get("policy_version", 1) in {2, 3}


def reference_fingerprint(project):
    job = project.get("job") or {}
    if job.get("editorial_fingerprint"):
        return job["editorial_fingerprint"]
    return next((r["editorial_fingerprint"] for r in reversed(project.get("revisions", []))
                 if r.get("editorial_fingerprint")), None)


def refined(project):
    """V3 behavior follows the producing job, never a later UI selection."""
    job = project.get("job") or {}
    if "editorial_policy" in job:
        return job["editorial_policy"] == 3
    if job.get("editorial_fingerprint") or job.get("response_contract_version"):
        return job.get("response_contract_version") == "2.5.0"
    return (project.get("writing_edition") or {}).get("policy_version") == 3
