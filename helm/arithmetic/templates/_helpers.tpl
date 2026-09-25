{{/*
Expand the name of the chart.
*/}}
{{- define "arithmetic.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name.
*/}}
{{- define "arithmetic.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "arithmetic.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "arithmetic.labels" -}}
app.kubernetes.io/name: {{ include "arithmetic.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "arithmetic.selectorLabels" -}}
app.kubernetes.io/name: {{ include "arithmetic.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Secret key helper: use value from values.yaml or generate a fresh one.
*/}}
{{- define "arithmetic.secretKey" -}}
{{- if .Values.secrets.secretKey -}}
{{- .Values.secrets.secretKey -}}
{{- else -}}
{{- randAlphaNum 64 -}}
{{- end -}}
{{- end -}}

{{- define "arithmetic.jwtSecret" -}}
{{- if .Values.secrets.jwtSecret -}}
{{- .Values.secrets.jwtSecret -}}
{{- else -}}
{{- randAlphaNum 64 -}}
{{- end -}}
{{- end -}}
