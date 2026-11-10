import argparse

from .dataset import SEQUENCES


def main():
    parser=argparse.ArgumentParser(description="DepthTrack RGB-D odometry laboratory")
    parser.add_argument("command",choices=("prepare","calibrate","benchmark","smoke"))
    parser.add_argument("--data",default="data/raw")
    parser.add_argument("--cache",default="data/features")
    parser.add_argument("--out",default="reports")
    parser.add_argument("--sequences",nargs="+",choices=SEQUENCES,default=list(SEQUENCES))
    args=parser.parse_args()
    if args.command=="prepare":
        from .features import extract
        for sequence in args.sequences:extract(args.data,sequence,args.cache)
    elif args.command=="calibrate":
        from .experiments import calibration
        calibration(args.data,args.cache,args.out+"/calibration.json")
    else:
        from .experiments import benchmark
        benchmark(args.data,args.cache,args.out,args.sequences,args.command=="smoke")


if __name__=="__main__":main()
