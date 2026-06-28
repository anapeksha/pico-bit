use embassy_net::tcp::TcpSocket;
use picoserve::io::{ErrorType, Read, Socket, Write};
use picoserve::{EmbassyRuntime, Timeouts};

use super::HTTP_PREFLIGHT_BYTES;

pub(super) struct PrefilteredSocket<'socket> {
    socket: TcpSocket<'socket>,
    prefix: [u8; HTTP_PREFLIGHT_BYTES],
    prefix_len: usize,
}

impl<'socket> PrefilteredSocket<'socket> {
    pub(super) fn new(
        socket: TcpSocket<'socket>,
        prefix: [u8; HTTP_PREFLIGHT_BYTES],
        prefix_len: usize,
    ) -> Self {
        Self {
            socket,
            prefix,
            prefix_len,
        }
    }
}

pub(super) struct PrefilteredReader<'a, R> {
    inner: R,
    prefix: &'a [u8],
    position: usize,
}

pub(super) struct PrefilteredWriter<W> {
    inner: W,
}

impl<R: ErrorType> ErrorType for PrefilteredReader<'_, R> {
    type Error = R::Error;
}

impl<R: Read> Read for PrefilteredReader<'_, R> {
    async fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::Error> {
        if self.position < self.prefix.len() {
            let available = self.prefix.len() - self.position;
            let count = available.min(buf.len());
            buf[..count].copy_from_slice(&self.prefix[self.position..self.position + count]);
            self.position += count;
            return Ok(count);
        }

        self.inner.read(buf).await
    }
}

impl<W: ErrorType> ErrorType for PrefilteredWriter<W> {
    type Error = W::Error;
}

impl<W: Write> Write for PrefilteredWriter<W> {
    async fn write(&mut self, buf: &[u8]) -> Result<usize, Self::Error> {
        self.inner.write(buf).await
    }

    async fn flush(&mut self) -> Result<(), Self::Error> {
        self.inner.flush().await
    }
}

impl<'socket> Socket<EmbassyRuntime> for PrefilteredSocket<'socket> {
    type Error = embassy_net::tcp::Error;
    type ReadHalf<'a>
        = PrefilteredReader<'a, embassy_net::tcp::TcpReader<'a>>
    where
        'socket: 'a;
    type WriteHalf<'a>
        = PrefilteredWriter<embassy_net::tcp::TcpWriter<'a>>
    where
        'socket: 'a;

    fn split(&mut self) -> (Self::ReadHalf<'_>, Self::WriteHalf<'_>) {
        let (reader, writer) = self.socket.split();

        (
            PrefilteredReader {
                inner: reader,
                prefix: &self.prefix[..self.prefix_len],
                position: 0,
            },
            PrefilteredWriter { inner: writer },
        )
    }

    async fn abort<T: picoserve::time::Timer<EmbassyRuntime>>(
        self,
        timeouts: &Timeouts,
        timer: &mut T,
    ) -> Result<(), picoserve::Error<Self::Error>> {
        Socket::<EmbassyRuntime>::abort(self.socket, timeouts, timer).await
    }

    async fn shutdown<T: picoserve::time::Timer<EmbassyRuntime>>(
        self,
        timeouts: &Timeouts,
        timer: &mut T,
    ) -> Result<(), picoserve::Error<Self::Error>> {
        Socket::<EmbassyRuntime>::shutdown(self.socket, timeouts, timer).await
    }
}
