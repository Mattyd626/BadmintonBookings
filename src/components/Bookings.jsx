import { useEffect, useState, useCallback } from "react";
import dayjs from "dayjs";

import {
  Card,
  CardContent,
  Typography,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Box,
  Chip,
  Stack
} from "@mui/material";

import {
  LocalizationProvider,
  DatePicker
} from "@mui/x-date-pickers";

import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

const API_BASE =
  "https://rare-years-circus-collections.trycloudflare.com/api/bookings";

export default function Bookings() {
  const [date, setDate] = useState(dayjs());
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);

      const formatted = date.format("DD/MM/YYYY");

      const res = await fetch(`${API_BASE}?date=${formatted}`);
      const data = await res.json();

      setSlots(data);
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Card sx={{ maxWidth: 900, mx: "auto", mt: 5, p: 2 }}>
        <CardContent>
          <Stack spacing={3}>
            <Typography variant="h5" fontWeight={600}>
              Badminton Court Availability
            </Typography>

            {/* Date Picker */}
            <DatePicker
              label="Select date"
              value={date}
              onChange={(newValue) => setDate(newValue)}
              disablePast
            />

            {/* Loading */}
            {loading && (
              <Box display="flex" justifyContent="center">
                <CircularProgress />
              </Box>
            )}

            {/* Table */}
            {!loading && slots.length > 0 && (
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell><b>Time</b></TableCell>
                    {slots[0].free.map((_, i) => (
                      <TableCell key={i} align="center">
                        <b>Court {i + 1}</b>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>

                <TableBody>
                  {slots.map((slot) => (
                    <TableRow key={slot.time}>
                      <TableCell>{slot.time}</TableCell>

                      {slot.free.map((isFree, i) => (
                        <TableCell key={i} align="center">
                          <Chip
                            label={isFree ? "Free" : "Booked"}
                            color={isFree ? "success" : "error"}
                            size="small"
                          />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Stack>
        </CardContent>
      </Card>
    </LocalizationProvider>
  );
}
