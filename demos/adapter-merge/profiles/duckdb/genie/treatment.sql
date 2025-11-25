-- Treatment query with optional filters
-- Parameters: regimen, min_survival

SELECT
    patient_id,
    regimen,
    os_months,
    response
FROM treatments
WHERE
    ($regimen IS NULL OR regimen = $regimen)
    AND
    ($min_survival IS NULL OR os_months >= $min_survival)
ORDER BY os_months DESC;
