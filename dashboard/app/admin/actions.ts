'use server'

import { createClient } from '@supabase/supabase-js'

// Admin actions use the service role key so they bypass RLS
function getAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!
  if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY not set in .env.local')
  return createClient(url, key)
}

export interface UpsertResult {
  success: boolean
  message: string
}

export async function upsertReading(formData: FormData): Promise<UpsertResult> {
  const indicator_id    = formData.get('indicator_id') as string
  const country_id      = formData.get('country_id') as string
  const date            = formData.get('date') as string
  const value           = formData.get('value') as string
  const notes           = formData.get('notes') as string
  const source_series_id_override = formData.get('source_series_id') as string | null

  if (!indicator_id || !date || !value) {
    return { success: false, message: 'Indicator, date and value are required.' }
  }

  const numValue = parseFloat(value)
  if (isNaN(numValue)) {
    return { success: false, message: 'Value must be a number.' }
  }

  const row = {
    indicator_id,
    country_id: country_id || null,
    date,
    value: numValue,
    source: 'manual',
    source_series_id: source_series_id_override || 'manual',
    notes: notes || null,
  }

  try {
    const supabase = getAdminClient()
    const { error } = await supabase
      .from('readings')
      .upsert(row, { onConflict: 'indicator_id,country_id,date' })

    if (error) return { success: false, message: error.message }
    return {
      success: true,
      message: `Saved: ${indicator_id}/${country_id || 'GLOBAL'} on ${date} = ${numValue}`,
    }
  } catch (err: any) {
    return { success: false, message: err.message ?? 'Unknown error' }
  }
}

export async function deleteReading(formData: FormData): Promise<UpsertResult> {
  const indicator_id = formData.get('indicator_id') as string
  const country_id   = formData.get('country_id') as string
  const date         = formData.get('date') as string

  try {
    const supabase = getAdminClient()
    let query = supabase
      .from('readings')
      .delete()
      .eq('indicator_id', indicator_id)
      .eq('date', date)

    if (country_id) {
      query = query.eq('country_id', country_id)
    } else {
      query = query.is('country_id', null)
    }

    const { error } = await query
    if (error) return { success: false, message: error.message }
    return { success: true, message: `Deleted ${indicator_id}/${country_id || 'GLOBAL'} on ${date}` }
  } catch (err: any) {
    return { success: false, message: err.message ?? 'Unknown error' }
  }
}
